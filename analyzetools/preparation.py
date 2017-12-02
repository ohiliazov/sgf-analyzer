import datetime
import hashlib
import os
import re
import sys
import config

from sgftools.sgflib import SGFParser

comment_regex = r"(?P<nickname>[\w\W]+)+: (?P<node_comment>[\w\W]+)+"


def import_sgf(filename):
    data = ""
    with open(filename, 'r', encoding="utf-8") as sgf_file:
        for line in sgf_file:
            data += line

    return SGFParser(data).parse()


def prepare_sgf(args):
    time_start = datetime.datetime.now()

    if args.verbosity > 0:
        print("Leela analysis started at %s" % time_start, file=sys.stderr)
        print("Game moves analysis: %d seconds per move" % args.analyze_time, file=sys.stderr)
        print("Variations analysis: %d seconds per move" % args.variations_time, file=sys.stderr)

    sgf_fn = args.path_to_sgf

    if not os.path.exists(sgf_fn):
        raise FileNotFoundError("No such file: %s" % sgf_fn)

    sgf = import_sgf(sgf_fn)

    if not os.path.exists(config.checkpoint_dir):
        os.mkdir(config.checkpoint_dir)

    base_hash = hashlib.md5(os.path.abspath(sgf_fn).encode()).hexdigest()
    base_dir = os.path.join(config.checkpoint_dir, base_hash)

    if not os.path.exists(base_dir):
        os.mkdir(base_dir)

    if args.verbosity > 1:
        print("Checkpoint dir: %s" % base_dir, file=sys.stderr)

    return sgf_fn, sgf, base_dir


def get_initial_values(cursor):
    node_boardsize = cursor.node.get('SZ')
    node_handicap = cursor.node.get('HA')
    node_rules = cursor.node.get('RU')
    node_komi = cursor.node.get('KM')

    board_size = int(node_boardsize.data[0]) if node_boardsize else 19

    if board_size != 19:
        print("WARNING: board size is not 19 so Leela could be much weaker and less accurate", file=sys.stderr)

    # Set handicap stones count
    if node_handicap and int(node_handicap.data[0]) > 1:
        handicap_stone_count = int(node_handicap.data[0])
    else:
        handicap_stone_count = 0

    is_handicap_game = bool(handicap_stone_count)

    # Set rules
    is_japanese_rules = node_rules and node_rules.data[0].lower() in ['jp', 'japanese', 'japan']

    # Set komi
    if node_komi:
        komi = float(node_komi.data[0])

        if is_handicap_game and is_japanese_rules:
            old_komi = komi
            komi = old_komi + handicap_stone_count
            print("Adjusting komi from %.1f to %.1f in converting Japanese rules with %d handicap to Chinese rules" % (
                old_komi, komi, handicap_stone_count), file=sys.stderr)
    else:
        if is_handicap_game:
            komi = 0.5
        else:
            komi = 6.5 if is_japanese_rules else 7.5
        print("Warning: Komi not specified, assuming %.1f" % komi, file=sys.stderr)

    return board_size, handicap_stone_count, is_handicap_game, is_japanese_rules, komi


def collect_requested_moves(cursor, args):
    comment_requests_analyze = {}
    comment_requests_variations = {}
    analyze_tasks_initial = 0
    variations_tasks_initial = 0
    move_num = -1

    while not cursor.atEnd:

        # Go to next node and increment move_num
        cursor.next()
        move_num += 1

        node_comment = cursor.node.get('C')

        # Store moves, requested for analysis and variations
        if node_comment:
            match = re.match(comment_regex, node_comment.data[0])

            if 'analyze' in match.group('node_comment'):
                comment_requests_analyze[move_num] = True

            if 'variations' in match.group('node_comment'):
                comment_requests_analyze[move_num] = True
                comment_requests_variations[move_num] = True

            # Wipe comments is needed
            if args.wipe_comments:
                node_comment.data[0] = ""
        analysis_mode = None

        if args.analyze_start <= move_num <= args.analyze_end:
            analysis_mode = 'analyze'

        if move_num in comment_requests_analyze or (move_num - 1) in comment_requests_analyze or (
                move_num - 1) in comment_requests_variations:
            analysis_mode = 'analyze'

        if move_num in comment_requests_variations:
            analysis_mode = 'variations'

        if analysis_mode == 'analyze':
            analyze_tasks_initial += 1
        elif analysis_mode == 'variations':
            analyze_tasks_initial += 1
            variations_tasks_initial += 1

    return comment_requests_analyze, comment_requests_variations, analyze_tasks_initial, variations_tasks_initial
