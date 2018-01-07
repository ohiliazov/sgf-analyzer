import datetime
import os
import time
import traceback

import arguments
import config
from analyzetools.analyze import do_analyze, next_move_pos
from analyzetools.variations import do_variations
from analyzetools.leelatools import add_moves_to_leela
from analyzetools.preparation import parse_sgf, prepare_checkpoint_dir, get_initial_values, collect_requested_moves
from sgftools import annotations
from sgftools.leela import Leela
from sgftools.utils import save_to_file, convert_position, graph_winrates
from sgftools.progressbar import ProgressBar
from sgftools.logger import analyzer_logger


class PlayedTwiceError(Exception):
    pass


def is_skipped(args, player_color):
    return (args.skip_white and player_color == "white") and not (args.skip_black and player_color == "black")


def analyze_sgf(args, sgf_to_analyze):
    time_start = datetime.datetime.now()

    analyzer_logger.info(f"File to analyze: {sgf_to_analyze}")
    analyzer_logger.info(f"Game analysis started.")
    analyzer_logger.info(f"Time settings: main line {args.analyze_time:d} seconds/move, "
                         f"variations {args.variations_time:d} seconds/move")

    sgf = parse_sgf(sgf_to_analyze)
    base_dir = prepare_checkpoint_dir(sgf)

    analyzer_logger.info(f"Checkpoint dir: {base_dir}")

    # Set up SGF cursor and get values from first node
    cursor = sgf.cursor()
    game_settings = get_initial_values(cursor)

    board_size = game_settings['board_size']
    handicap_stones = game_settings['handicap_stones']
    komi = game_settings['komi']

    if board_size != 19:
        analyzer_logger.warning("Board size is not 19 so Leela could be much weaker and less accurate.")

    # First loop for comments parsing

    moves_to_analyze, moves_to_variations = collect_requested_moves(cursor, args)

    analyze_tasks = len(moves_to_analyze)
    variations_tasks = len(moves_to_variations)
    analyze_tasks_done = 0
    variations_tasks_done = 0

    leela = Leela(board_size=board_size,
                  path_to_exec=args.path_to_leela,
                  handicap_stones=handicap_stones,
                  komi=komi,
                  seconds_per_search=args.analyze_time)

    collected_stats = {}
    collected_move_lists = {}
    best_moves = {}

    try:
        progress_bar = ProgressBar(max_value=analyze_tasks)

        leela.start()
        progress_bar.start()

        cursor = sgf.cursor()
        add_moves_to_leela(cursor, leela)

        move_num = -1
        prev_stats = {}
        prev_move_list = []
        has_prev = False
        previous_player = None

        analyzer_logger.info(f"Executing analysis for {analyze_tasks} moves")

        # analyze main line, without variations
        while not cursor.atEnd:
            cursor.next()
            move_num += 1
            this_move = add_moves_to_leela(cursor, leela)

            current_player = 'black' if 'W' in cursor.node else 'white'

            if previous_player == current_player:
                raise PlayedTwiceError

            if move_num in moves_to_analyze:
                stats, move_list, skipped = do_analyze(leela, base_dir, args.verbosity, args.analyze_time)

                # Here we store ALL statistics
                collected_stats[move_num] = stats
                collected_move_lists[move_num] = move_list

                if move_list and 'winrate' in move_list[0]:
                    best_moves[move_num] = move_list[0]

                delta = 0.0

                if 'winrate' in stats and (move_num - 1) in best_moves:
                    if this_move != best_moves[move_num - 1]['pos']:
                        delta = stats['winrate'] - best_moves[move_num - 1]['winrate']
                        delta = min(0.0, (-delta if leela.whose_turn() == "black" else delta))

                    if -delta > args.analyze_threshold:
                        (delta_comment, delta_lb_values) = annotations.format_delta_info(delta, this_move, board_size)
                        annotations.annotate_sgf(cursor, delta_comment, delta_lb_values, [])

                if has_prev and delta <= -args.variations_threshold and not is_skipped(args, previous_player):
                    if (move_num - 1) not in moves_to_variations:
                        variations_tasks += 1
                    moves_to_variations[move_num - 1] = True

                if args.show_winrate and -delta > args.analyze_threshold:
                    progress_bar.set_message(f'winrate {(stats["winrate"]*100):.2f}% | '
                                             f'{current_player} '
                                             f'{convert_position(board_size, this_move):<3} | '
                                             f'delta {(delta*100):.2f}%')

                next_game_move = next_move_pos(cursor)

                annotations.annotate_sgf(cursor,
                                         annotations.format_winrate(stats, move_list, board_size, next_game_move),
                                         [], [])

                if has_prev and ((move_num - 1) in moves_to_analyze and -delta > args.analyze_threshold or (
                        move_num - 1) in moves_to_variations):
                    if not (args.skip_white and previous_player == "white") and not (
                            args.skip_black and previous_player == "black"):

                        def filter_move_list(move_list):
                            visit_sums = sum([move['visits'] for move in move_list])
                            return [move for move in move_list if
                                    move['visits'] / visit_sums > config.move_list_threshold]

                        (analysis_comment, lb_values, tr_values) = annotations.format_analysis(
                            prev_stats, filter_move_list(prev_move_list), this_move, board_size)
                        cursor.previous()
                        # adding comment to sgf with suggested alternative variations
                        annotations.annotate_sgf(cursor, analysis_comment, lb_values, tr_values)
                        cursor.next()

                prev_stats = stats
                prev_move_list = move_list
                has_prev = True
                analyze_tasks_done += 1

                # save to file results with analyzing main line
                save_to_file(sgf_to_analyze, sgf)

                if not skipped:

                    if args.win_graph and len(collected_stats) > 1:
                        graph_winrates(collected_stats, sgf_to_analyze)

                progress_bar.update(analyze_tasks_done, analyze_tasks)
                progress_bar.set_message(None)

            else:
                prev_stats = {}
                prev_move_list = []
                has_prev = False

            previous_player = current_player

        progress_bar.finish()
        leela.stop()
        leela.clear_history()

        if args.win_graph:
            graph_winrates(collected_stats, sgf_to_analyze)

        # Now fill in variations for everything we need (suggested variations)
        progress_bar = ProgressBar(max_value=variations_tasks)
        progress_bar.start()

        leela = Leela(board_size=board_size,
                      path_to_exec=args.path_to_leela,
                      handicap_stones=handicap_stones,
                      komi=komi,
                      seconds_per_search=args.variations_time)

        move_num = -1
        cursor = sgf.cursor()
        leela.start()
        add_moves_to_leela(cursor, leela)

        analyzer_logger.info(
            f"Exploring variations for {variations_tasks:d} moves with {args.variations_depth:d} steps")

        while not cursor.atEnd:
            cursor.next()
            move_num += 1
            add_moves_to_leela(cursor, leela)

            if move_num not in moves_to_variations:
                continue

            stats, move_list = collected_stats[move_num], collected_move_lists[move_num]

            if 'bookmoves' in stats or len(move_list) <= 0:
                continue

            next_game_move = next_move_pos(cursor)

            do_variations(cursor, leela, stats, move_list, board_size, next_game_move, base_dir, args)
            variations_tasks_done += 1

            save_to_file(sgf_to_analyze, sgf)
            progress_bar.update(variations_tasks_done, variations_tasks)

        progress_bar.finish()

    except:
        analyzer_logger.critical(f"{traceback.format_exc()}")
        traceback.print_exc()
    finally:
        leela.stop()

    time_stop = datetime.datetime.now()

    analyzer_logger.info(f"Leela analysis stopped at {time_stop.strftime('%H:%M:%S')}")
    analyzer_logger.info(f"Elapsed time: {time_stop - time_start}")

    # delay in case of sequential running of several analysis
    time.sleep(1)


if __name__ == '__main__':
    args = arguments.parser.parse_args()

    if os.path.isdir(args.path_to_sgf):
        games_to_analyze = [os.path.join(args.path_to_sgf, file) for file in os.listdir(args.path_to_sgf)
                            if file.endswith('.sgf') and not file.endswith('_analyzed.sgf')]
    else:
        games_to_analyze = [args.path_to_sgf]

    for game in games_to_analyze:
        analyze_sgf(args, game)
