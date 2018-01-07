import os
import pickle
import sys
import traceback

import config
from sgftools.logger import analyzer_logger

def retry_analysis(restarts):
    def wrapper(fn):
        def try_analysis(*args, **kwargs):
            if not isinstance(restarts, int) or not restarts:
                return fn(*args, **kwargs)
            for i in range(restarts):
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    traceback.print_exc()
                    if restarts < i:
                        raise
                    print("Error in leela, retrying analysis...", file=sys.stderr)
        return try_analysis
    return wrapper


@retry_analysis(config.restarts)
def do_analyze(leela, base_dir, seconds_per_search):
    ckpt_hash = 'analyze_' + leela.history_hash() + "_" + str(seconds_per_search) + "sec"
    ckpt_fn = os.path.join(base_dir, ckpt_hash)

    if os.path.exists(ckpt_fn) and not config.skip_checkpoints:
        skipped = True
        analyzer_logger.info("Loading checkpoint file: %s" % ckpt_fn)
        with open(ckpt_fn, 'rb') as ckpt_file:
            stats, move_list = pickle.load(ckpt_file)
    else:
        skipped = False
        leela.clear_board()
        leela.go_to_position()
        stats, move_list = leela.analyze()
        with open(ckpt_fn, 'wb') as ckpt_file:
            pickle.dump((stats, move_list), ckpt_file)

    analyzer_logger.debug(f"Move stats: {stats}")
    analyzer_logger.debug(f"Move list: {move_list}")
    return stats, move_list, skipped


def next_move_pos(cursor):
    mv = None

    if not cursor.atEnd:
        cursor.next()
        if 'W' in cursor.node.keys():
            mv = cursor.node['W'].data[0]
        if 'B' in cursor.node.keys():
            mv = cursor.node['B'].data[0]
        cursor.previous()

    return mv
