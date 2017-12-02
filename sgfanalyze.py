import datetime
import sys
import time
import traceback

import arguments
import sgftools.utils as utils
from analyzetools.analyze import do_analyze
from analyzetools.variations import do_variations
from analyzetools.leelatools import add_moves_to_leela
from analyzetools.preparation import prepare_sgf, get_initial_values, collect_requested_moves
from sgftools import annotations, progressbar
from sgftools.leela import Leela
from sgftools.utils import save_to_file

default_analyze_thresh = 0.010
default_var_thresh = 0.010

if __name__ == '__main__':

    time_start = datetime.datetime.now()

    args = arguments.parser.parse_args()
    sgf_fn, sgf, base_dir = prepare_sgf(args)

    # Set up SGF cursor and get values from first node
    cursor = sgf.cursor()
    board_size, handicap_stone_count, is_handicap_game, is_japanese_rules, komi = get_initial_values(cursor)

    # First loop for comments parsing

    analyze_request, variations_request, analyze_tasks, variations_tasks = collect_requested_moves(cursor, args)
    analyze_tasks_done = 0
    variations_tasks_done = 0


    def approx_tasks_done():
        return analyze_tasks_done + (variations_tasks_done * args.nodes_per_variation)


    def approx_tasks_max():
        return analyze_tasks + (variations_tasks * args.nodes_per_variation)


    print("Executing approx %d analysis steps" % approx_tasks_max(), file=sys.stderr)

    progress_bar = progressbar.ProgressBar(max_value=approx_tasks_max())
    progress_bar.start()


    def refresh_progress_bar():
        progress_bar.update(approx_tasks_done(), approx_tasks_max())


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
        move_num = -1
        cursor = sgf.cursor()
        prev_stats = {}
        prev_move_list = []
        has_prev = False

        leela.start()
        add_moves_to_leela(cursor, leela)

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
                save_to_file(sgf_fn, sgf)

                if args.win_graph and len(collected_winrates) > 0 and not skipped:
                    utils.graph_winrates(collected_winrates, sgf_fn)

                refresh_progress_bar()

                # until now analyze of main line, without sub-variations

            else:
                prev_stats = {}
                prev_move_list = []
                has_prev = False

        leela.stop()
        leela.clear_history()

        if args.win_graph:
            utils.graph_winrates(collected_winrates, sgf_fn)

        # Now fill in variations for everything we need (suggested variations)
        move_num = -1
        cursor = sgf.cursor()
        leela.start()
        add_moves_to_leela(cursor, leela)

        while not cursor.atEnd:
            cursor.next()
            move_num += 1
            add_moves_to_leela(cursor, leela)

            if move_num not in needs_variations:
                continue

            stats, move_list = needs_variations[move_num]
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
            save_to_file(sgf_fn, sgf)

            refresh_progress_bar()
    except:
        traceback.print_exc()
        print("Failure, reporting partial results...", file=sys.stderr)
    finally:
        leela.stop()

    progress_bar.finish()

    # Save final results into file
    save_to_file(sgf_fn, sgf)

    time_stop = datetime.datetime.now()

    if args.verbosity > 0:
        print("Leela analysis stopped at %s" % time_stop, file=sys.stderr)
        print("Elapsed time: %s" % (time_stop - time_start), file=sys.stderr)

    # delay in case of sequential running of several analysis
    time.sleep(1)
