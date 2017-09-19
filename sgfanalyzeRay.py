import os
import sys
import argparse
import hashlib
import pickle
import traceback
import time



from sgftools import gotools, ray, annotations, progressbar, sgflib


DEFAULT_STDEV = 0.22
RESTART_COUNT = 1

default_analyze_thresh = 0.030
default_var_thresh = 0.030


def add_moves_to_leela(C, leela):
    this_move = None

    if 'W' in C.node.keys():
        this_move = C.node['W'].data[0]
        ray.add_move('white', this_move)

    if 'B' in C.node.keys():
        this_move = C.node['B'].data[0]
        ray.add_move('black', this_move)

    # SGF commands to add black or white stones, often used for setting up handicap and such
    if 'AB' in C.node.keys():
        for move in C.node['AB'].data:
            ray.add_move('black', move)

    if 'AW' in C.node.keys():
        for move in C.node['AW'].data:
            ray.add_move('white', move)

    return this_move


def do_analyze(ray, base_dir, verbosity):
    ckpt_hash = 'analyze_' + ray.history_hash() + "_" + str(ray.seconds_per_search) + "sec"
    ckpt_fn = os.path.join(base_dir, ckpt_hash)

    if verbosity > 2:
        print("Looking for checkpoint file: %s" % ckpt_fn, file=sys.stderr)

    if os.path.exists(ckpt_fn):
        if verbosity > 1:
            print("Loading checkpoint file: %s" % ckpt_fn, file=sys.stderr)
        with open(ckpt_fn, 'rb') as ckpt_file:
            stats, move_list = pickle.load(ckpt_file)
            ckpt_file.close()
    else:
        ray.reset()
        ray.goto_position()
        stats, move_list = ray.analyze()
        with open(ckpt_fn, 'wb') as ckpt_file:
            pickle.dump((stats, move_list), ckpt_file)
            ckpt_file.close()

    return stats, move_list



if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    required = parser.add_argument_group('required named arguments')

    parser.add_argument("SGF_FILE", help="SGF file to analyze")
    parser.add_argument("--save_to_file", dest='save_to_file',
                        help="File to save results of analyze, if skipped - use source filename with adding 'analyzed'")

    required.add_argument('--leela', dest='executable', required=True, metavar="CMD",
                          help="Command to run Leela executable")

    parser.add_argument('--analyze-thresh', dest='analyze_threshold', default=default_analyze_thresh, type=float,
                        metavar="T",
                        help="Display analysis on moves losing approx at least this much win rate when the game is close (default=0.03)")
    parser.add_argument('--var-thresh', dest='variations_threshold', default=default_var_thresh, type=float,
                        metavar="T",
                        help="Explore variations on moves losing approx at least this much win rate when the game is close (default=0.03)")
    parser.add_argument('--secs-per-search', dest='seconds_per_search', default=10, type=float, metavar="S",
                        help="How many seconds to use per search (default=10)")
    parser.add_argument('--nodes-per-var', dest='nodes_per_variation', default=8, type=int, metavar="N",
                        help="How many nodes to explore with leela in each variation tree (default=8)")
    parser.add_argument('--num_to_show', dest='num_to_show', default=0, type=int,
                        help="Number of moves to show from the sequence of suggested moves (default=0)")

    parser.add_argument('--win-graph', dest='win_graph', action='store_true',
                        help="Build pdf graph of win rate, must have matplotlib installed")
    parser.add_argument('--wipe-comments', dest='wipe_comments', action='store_true',
                        help="Remove existing comments from the main line of the SGF file")

    parser.add_argument('--start', dest='analyze_start', default=0, type=int, metavar="MOVENUM",
                        help="Analyze game starting at this move (default=0)")
    parser.add_argument('--stop', dest='analyze_end', default=1000, type=int, metavar="MOVENUM",
                        help="Analyze game stopping at this move (default=1000)")

    parser.add_argument('-v', '--verbosity', default=0, type=int, metavar="V",
                        help="Set the verbosity level, 0: progress only, 1: progress+status, 2: progress+status+state")

    parser.add_argument('--cache', dest='ckpt_dir', metavar="DIR", default=os.path.expanduser('~/.leela_checkpoints'),
                        help="Set a directory to cache partially complete analyses, default ~/.leela_checkpoints")
    parser.add_argument('--restarts', default=2, type=int, metavar="N",
                        help="If leela crashes, retry the analysis step this many times before reporting a failure")

    parser.add_argument('--skip-white', dest='skip_white', action='store_true',
                        help="Do not display analysis or explore variations for white mistakes")
    parser.add_argument('--skip-black', dest='skip_black', action='store_true',
                        help="Do not display analysis or explore variations for black mistakes")


    args = parser.parse_args()
    sgf_fn = args.SGF_FILE

    # if no file name to save analyze results provided - it will use original source file with concat 'analyzed'
    if not args.save_to_file:
        args.save_to_file = args.SGF_FILE.split('.')[0] + '_analyzed.sgf'

    if not os.path.exists(sgf_fn):
        parser.error("No such file: %s" % (sgf_fn))
    sgf = gotools.import_sgf(sgf_fn)

    RESTART_COUNT = args.restarts

    if not os.path.exists(args.ckpt_dir):
        os.mkdir(args.ckpt_dir)

    base_hash = hashlib.md5(os.path.abspath(sgf_fn).encode()).hexdigest()
    base_dir = os.path.join(args.ckpt_dir, base_hash)

    if not os.path.exists(base_dir):
        os.mkdir(base_dir)

    if args.verbosity > 1:
        print("Checkpoint dir: %s" % base_dir, file=sys.stderr)

    comment_requests_analyze = {}
    comment_requests_variations = {}
    C = sgf.cursor()

    if 'SZ' in C.node.keys():
        board_size = int(C.node['SZ'].data[0])
    else:
        board_size = 19

    if board_size != 19:
        print("Warning: board size is not 19 so Leela could be much weaker and less accurate", file=sys.stderr)

        if args.analyze_threshold == default_analyze_thresh or args.variations_threshold == default_var_thresh:
            print("Warning: Consider also setting --analyze-thresh and --var-thresh higher", file=sys.stderr)

    move_num = -1
    C = sgf.cursor()

    while not C.atEnd:
        C.next()
        move_num += 1

        if 'C' in C.node.keys():
            if 'analyze' in C.node['C'].data[0]:
                comment_requests_analyze[move_num] = True

            if 'variations' in C.node['C'].data[0]:
                comment_requests_variations[move_num] = True

    if args.wipe_comments:
        C = sgf.cursor()
        cnode = C.node

        if cnode.has_key('C'):
            cnode['C'].data[0] = ""

        while not C.atEnd:
            C.next()
            cnode = C.node

            if cnode.has_key('C'):
                cnode['C'].data[0] = ""

    C = sgf.cursor()
    is_handicap_game = False
    handicap_stone_count = 0

    if 'HA' in C.node.keys() and int(C.node['HA'].data[0]) > 1:
        is_handicap_game = True
        handicap_stone_count = int(C.node['HA'].data[0])

    is_japanese_rules = False
    komi = 7.5

    if 'RU' in C.node.keys():
        rules = C.node['RU'].data[0].lower()
        is_japanese_rules = (rules == 'jp' or rules == 'japanese' or rules == 'japan')
        komi = 6.5

    if 'KM' in C.node.keys():
        komi = float(C.node['KM'].data[0])

        if is_handicap_game and is_japanese_rules:
            old_komi = komi
            komi = old_komi + handicap_stone_count
            print("Adjusting komi from %f to %f in converting Japanese rules with %d handicap to Chinese rules" % (
                old_komi, komi, handicap_stone_count), file=sys.stderr)

        # fix issue when komi is not set in given sgf, for example from Fox server
        if komi == 0 and not is_handicap_game:
            komi = 6.5

    else:
        if is_handicap_game:
            komi = 0.5
        print("Warning: Komi not specified, assuming %f" % komi, file=sys.stderr)

    ray = ray.CLI(executable=args.executable,
                      seconds_per_search=args.seconds_per_search,
                      verbosity=args.verbosity)

    collected_winrates = {}
    collected_best_moves = {}
    collected_best_move_winrates = {}
    needs_variations = {}

    try:
        move_num = -1
        C = sgf.cursor()
        prev_stats = {}
        prev_move_list = []
        has_prev = False

        ray.start()
        add_moves_to_leela(C, ray)

        # analyze main line, without variations
        while not C.atEnd:
            C.next()
            move_num += 1
            this_move = add_moves_to_leela(C, ray)
            current_player = ray.whoseturn()
            prev_player = "white" if current_player == "black" else "black"


            stats, move_list = do_analyze(ray, base_dir, args.verbosity)

            if 'winrate' in stats and stats['visits'] > 100:
                collected_winrates[move_num] = (current_player, stats['winrate'])

            if len(move_list) > 0 and 'winrate' in move_list[0]:
                collected_best_moves[move_num] = move_list[0]['pos']
                collected_best_move_winrates[move_num] = move_list[0]['winrate']

            delta = 0.0
            transdelta = 0.0

            next_game_move = None




            ray.stop()
            ray.clear_history()


    except:
        traceback.print_exc()
        print("Failure, reporting partial results...", file=sys.stderr)
    finally:
        ray.stop()


    #print(sgf)

    # delay in case of sequential running of several analysis
    time.sleep(1)

