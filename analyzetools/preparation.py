import datetime
import hashlib
import os
import sys
import config

from sgftools.sgflib import SGFParser


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
