import datetime
import sys
import time
import traceback

import arguments
from analyzetools.analyze import do_analyze
from analyzetools.variations import do_variations
from analyzetools.leelatools import add_moves_to_leela
from analyzetools.preparation import parse_sgf, prepare_checkpoint_dir, get_initial_values, collect_requested_moves
from sgftools import annotations
from sgftools.leela import Leela
from sgftools.utils import save_to_file, convert_position, graph_winrates
from sgftools.progressbar import ProgressBar

if __name__ == '__main__':

    time_start = datetime.datetime.now()

    args = arguments.parser.parse_args()

    if args.verbosity > 0:
        print(f"Leela analysis started at {time_start.strftime('%H:%M:%S')}\n"
              f"Game moves analysis: {args.analyze_time:d} seconds per move\n"
              f"Variations analysis: {args.variations_time:d} seconds per move", file=sys.stderr)

    sgf = parse_sgf(args.path_to_sgf)
    base_dir = prepare_checkpoint_dir(sgf)

    if args.verbosity > 1:
        print("Checkpoint dir: %s" % base_dir, file=sys.stderr)

    # Set up SGF cursor and get values from first node
    cursor = sgf.cursor()
    game_settings = get_initial_values(cursor)

    board_size = game_settings['board_size']
    is_handicap_game = game_settings['is_handicap_game']
    komi = game_settings['komi']

    if board_size != 19:
        print("WARNING: board size is not 19 so Leela could be much weaker and less accurate", file=sys.stderr)

    # First loop for comments parsing

    analyze_request, variations_request, analyze_tasks, variations_tasks = collect_requested_moves(cursor, args)
    analyze_tasks_done = 0
    variations_tasks_done = 0

    leela = Leela(board_size=board_size,
                  executable=args.path_to_leela,
                  is_handicap_game=is_handicap_game,
                  komi=komi,
                  seconds_per_search=args.analyze_time,
                  verbosity=args.verbosity)

    collected_winrates = {}
    collected_best_moves = {}
    collected_best_move_winrates = {}
    needs_variations = {}

    try:
        progress_bar = ProgressBar(max_value=analyze_tasks)
        print(f"Executing analysis for {analyze_tasks} moves", file=sys.stderr)

        leela.start()
        progress_bar.start()

        cursor = sgf.cursor()
        add_moves_to_leela(cursor, leela)

        move_num = -1
        prev_stats = {}
        prev_move_list = []
        has_prev = False

        # analyze main line, without variations
        while not cursor.atEnd:
            cursor.next()
            move_num += 1
            this_move = add_moves_to_leela(cursor, leela)
            current_player = leela.whose_turn()
            prev_player = "white" if current_player == "black" else "black"

            if ((args.analyze_start <= move_num <= args.analyze_end) or
                    (move_num in analyze_request) or
                    ((move_num - 1) in analyze_request) or
                    (move_num in variations_request) or
                    ((move_num - 1) in variations_request)):

                stats, move_list, skipped = do_analyze(leela, base_dir, args.verbosity, args.analyze_time)

                if 'winrate' in stats and stats['visits'] > 100:
                    collected_winrates[move_num] = (current_player, stats['winrate'])

                if len(move_list) > 0 and 'winrate' in move_list[0]:
                    collected_best_moves[move_num] = move_list[0]['pos']
                    collected_best_move_winrates[move_num] = move_list[0]['winrate']

                delta = 0.0

                if 'winrate' in stats and (move_num - 1) in collected_best_moves:
                    if this_move != collected_best_moves[move_num - 1]:
                        delta = stats['winrate'] - collected_best_move_winrates[move_num - 1]
                        delta = min(0.0, (-delta if leela.whose_turn() == "black" else delta))

                    if delta <= -args.analyze_threshold:
                        (delta_comment, delta_lb_values) = annotations.format_delta_info(delta, this_move, board_size)
                        annotations.annotate_sgf(cursor, delta_comment, delta_lb_values, [])

                if has_prev and (delta <= -args.variations_threshold or (move_num - 1) in variations_request):
                    if not (args.skip_white and prev_player == "white") and not (
                            args.skip_black and prev_player == "black"):
                        needs_variations[move_num - 1] = (prev_stats, prev_move_list)

                        if (move_num - 1) not in variations_request:
                            variations_tasks += 1

                if args.show_winrate and -delta > args.analyze_threshold:
                    progress_bar.set_message(f'winrate {(stats["winrate"]*100):.2f}% | '
                                             f'{current_player} '
                                             f'{convert_position(board_size, this_move):<3} | '
                                             f'delta {(delta*100):.2f}%')

                next_game_move = None

                if not cursor.atEnd:
                    cursor.next()

                    if 'W' in cursor.node.keys():
                        next_game_move = cursor.node['W'].data[0]

                    if 'B' in cursor.node.keys():
                        next_game_move = cursor.node['B'].data[0]

                    cursor.previous()

                annotations.annotate_sgf(cursor,
                                         annotations.format_winrate(stats, move_list, board_size, next_game_move),
                                         [], [])

                if has_prev and ((move_num - 1) in analyze_request or (
                        move_num - 1) in variations_request or delta <= -args.analyze_threshold):
                    if not (args.skip_white and prev_player == "white") and not (
                            args.skip_black and prev_player == "black"):
                        (analysis_comment, lb_values, tr_values) = annotations.format_analysis(prev_stats,
                                                                                               prev_move_list,
                                                                                               this_move)
                        cursor.previous()
                        # adding comment to sgf with suggested alternative variations
                        annotations.annotate_sgf(cursor, analysis_comment, lb_values, tr_values)
                        cursor.next()

                prev_stats = stats
                prev_move_list = move_list
                has_prev = True
                analyze_tasks_done += 1

                # save to file results with analyzing main line
                save_to_file(args.path_to_sgf, sgf)

                if not skipped:
                    progress_bar.update(analyze_tasks_done, analyze_tasks)

                    if args.win_graph and len(collected_winrates) > 1:
                        graph_winrates(collected_winrates, args.path_to_sgf)

                progress_bar.set_message(None)

            else:
                prev_stats = {}
                prev_move_list = []
                has_prev = False

        progress_bar.finish()
        leela.stop()
        leela.clear_history()

        if args.win_graph:
            graph_winrates(collected_winrates, args.path_to_sgf)

        # Now fill in variations for everything we need (suggested variations)
        print("Exploring variations for %d moves with %d steps" % (variations_tasks, args.variations_depth),
              file=sys.stderr)

        progress_bar = ProgressBar(max_value=variations_tasks)
        progress_bar.start()

        move_num = -1
        cursor = sgf.cursor()
        leela.start()
        add_moves_to_leela(cursor, leela)

        while not cursor.atEnd:
            cursor.next()
            move_num += 1

            if move_num not in needs_variations:
                continue

            stats, move_list = needs_variations[move_num]

            if 'bookmoves' in stats or len(move_list) <= 0:
                continue

            add_moves_to_leela(cursor, leela)
            next_game_move = None

            if not cursor.atEnd:
                cursor.next()

                if 'W' in cursor.node.keys():
                    next_game_move = cursor.node['W'].data[0]

                if 'B' in cursor.node.keys():
                    next_game_move = cursor.node['B'].data[0]

                cursor.previous()

            do_variations(cursor, leela, stats, move_list, board_size, next_game_move, base_dir, args)
            variations_tasks_done += 1

            # save to file results with analyzing variations
            save_to_file(args.path_to_sgf, sgf)

            progress_bar.update(variations_tasks_done, variations_tasks)

        progress_bar.finish()

    except:
        traceback.print_exc()
        print("Failure, reporting partial results...", file=sys.stderr)
    finally:
        leela.stop()

    # Save final results into file
    save_to_file(args.path_to_sgf, sgf)

    time_stop = datetime.datetime.now()

    if args.verbosity > 0:
        print("Leela analysis stopped at %s" % time_stop.strftime('%H:%M:%S'), file=sys.stderr)
        print("Elapsed time: %s" % (time_stop - time_start), file=sys.stderr)

    # delay in case of sequential running of several analysis
    time.sleep(1)
