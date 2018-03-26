import argparse
import hashlib
import os
import pickle
import tkinter as tk
from tkinter import filedialog

import numpy as np
from yaml import load

import settings
from bot_engines import LeelaCLI, LeelaZeroCLI
from log import logger, log_stream
from sgflib import Node, Property, SGFParser
from sgftools import annotations
from sgftools.utils import convert_position

with open(settings.PATH_TO_CONFIG) as yaml_stream:
    yaml_data = load(yaml_stream)

CONFIG = yaml_data['config']
BOTS = yaml_data['bots']

log_stream.setLevel(yaml_data['log_level'])


def retry_analysis(restarts):
    def wrapper(fn):
        def try_analysis(*args, **kwargs):
            if not isinstance(restarts, int) or not restarts:
                return fn(*args, **kwargs)
            for i in range(restarts):
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    if restarts < i:
                        raise
                    logger.error("Exception during analysis, retrying analysis...")

        return try_analysis

    return wrapper


def parse_cmd_line():
    parser = argparse.ArgumentParser(argument_default=None)
    parser.add_argument('-b', '--bot', default=BOTS['default'],
                        dest='bot', help="Settings from config.yaml to use.")
    parser.add_argument('--no-vars', dest='no_variations', action='store_true', help="Skip variations analysis.")

    return parser.parse_args()


def filter_move_list(move_list):
    visit_sums = sum([move['visits'] for move in move_list])
    return [move for move in move_list if move['visits'] / visit_sums > CONFIG['move_list_threshold']]


class BotException(Exception):
    pass


class BotAnalyzer:
    def __init__(self, path_to_sgf, bot_config):
        self._path_to_sgf = path_to_sgf
        self._bot_config = bot_config

        self.sgf_data = None
        self.cursor = None
        self.analyzer = None
        self.bot = None
        self.base_dir = None

        self.moves_to_analyze = {}
        self.moves_to_variations = {}

        self.best_moves = {}
        self.all_stats = {}
        self.all_move_lists = {}

    def factory(self):

        kwargs = {'board_size': self.board_size,
                  'komi': self.komi,
                  'handicap': self.handicap}
        bot_settings = BOTS[self._bot_config]
        kwargs.update(bot_settings)

        if bot_settings['bot_type'] == 'leela':
            return LeelaCLI(**kwargs)

        elif bot_settings['bot_type'] == 'leela-zero':
            return LeelaZeroCLI(**kwargs)

    @property
    def board_size(self):
        node_boardsize = self.cursor.node.get('SZ')
        if node_boardsize:
            board_size = int(node_boardsize.data[0])
            if board_size != 19:
                logger.warning("Board size is not 19 so analysis could be very inaccurate.")
        else:
            board_size = 19

        return board_size

    @property
    def handicap(self):
        node_handicap = self.cursor.node.get('HA')
        if node_handicap:
            return int(node_handicap.data[0])
        else:
            return 0

    @property
    def japanese_rules(self):
        node_rules = self.cursor.node.get('RU')
        return node_rules and node_rules.data[0].lower() in ['jp', 'japanese', 'japan']

    @property
    def komi(self):
        """ Returns adjusted komi."""
        node_komi = self.cursor.node.get('KM')

        if node_komi:
            komi = round(float(node_komi.data[0]), 1)

            if self.japanese_rules:
                komi += self.handicap

        elif self.handicap:
            komi = 0.5

        else:
            komi = 6.5 if self.japanese_rules else 7.5

        return komi

    def parse_sgf_file(self):
        """ Returns parsed Collection from sgf"""
        with open(self._path_to_sgf, 'r', encoding="utf-8") as sgf_file:
            data = "".join([line for line in sgf_file])
        self.sgf_data = SGFParser(data).parse()

    def save_to_file(self):
        file_name, file_ext = os.path.splitext(self._path_to_sgf)
        path_to_save = f"{file_name}_{self._bot_config}{file_ext}"
        with open(path_to_save, mode='w', encoding='utf-8') as f:
            f.write(str(self.sgf_data))

    def graph_winrates(self):
        import matplotlib
        matplotlib.use('Agg')

        import matplotlib.pyplot as plt

        if len(self.all_stats) <= 2:
            return

        first_move_num = min(self.all_stats.keys())
        last_move_num = max(self.all_stats.keys())
        x = []
        y = []
        for move_num in sorted(self.all_stats.keys()):
            if 'winrate' not in self.all_stats[move_num]:
                continue
            x.append(move_num)
            y.append(self.all_stats[move_num]['winrate'])

        plt.figure()

        # fill graph with horizontal coordinate lines, step 0.25
        for xc in np.arange(0, 1, 0.025):
            plt.axhline(xc, first_move_num, last_move_num, linewidth=0.04, color='0.7')

        # add single central horizontal line
        plt.axhline(0.50, first_move_num, last_move_num, linewidth=0.3, color='0.2')

        # main graph of win rate changes
        plt.plot(x, y, color='#ff0000', marker='.', markersize=2.5, linewidth=0.6)

        # set range limits for x and y axes
        plt.xlim(0, last_move_num)
        plt.ylim(0, 1)

        # set size of numbers on axes
        plt.yticks(np.arange(0, 1.05, 0.05), fontsize=6)
        plt.yticks(fontsize=6)

        # add labels to axes
        plt.xlabel("Move Number", fontsize=10)
        plt.ylabel("Win Rate", fontsize=12)

        # in this script for pdf it use the same file name as provided sgf file to avoid extra parameters
        file_name = os.path.splitext(self._path_to_sgf)[0]
        file_name = f"{file_name}_{self._bot_config}.pdf"
        plt.savefig(file_name, dpi=200, format='pdf', bbox_inches='tight')
        plt.close()

    def add_moves_to_bot(self):
        this_move = None

        if 'W' in self.cursor.node.keys():
            this_move = self.cursor.node['W'].data[0]
            self.bot.add_move_to_history('white', this_move)

        if 'B' in self.cursor.node.keys():
            this_move = self.cursor.node['B'].data[0]
            self.bot.add_move_to_history('black', this_move)

        # SGF commands to add black or white stones, often used for setting up handicap and such
        if 'AB' in self.cursor.node.keys():
            for move in self.cursor.node['AB'].data:
                self.bot.add_move_to_history('black', move)

        if 'AW' in self.cursor.node.keys():
            for move in self.cursor.node['AW'].data:
                self.bot.add_move_to_history('white', move)

        return this_move

    def next_move_pos(self):
        mv = None

        if not self.cursor.atEnd:
            self.cursor.next()
            if 'W' in self.cursor.node.keys():
                mv = self.cursor.node['W'].data[0]
            if 'B' in self.cursor.node.keys():
                mv = self.cursor.node['B'].data[0]
            self.cursor.previous()

        return mv

    def do_analyze(self):
        ckpt_hash = f"{self.bot.history_hash()}_{self.bot.time_per_move}_sec"
        ckpt_fn = os.path.join(self.base_dir, ckpt_hash)

        if os.path.exists(ckpt_fn):
            logger.debug("Loading checkpoint file: %s", ckpt_fn)
            with open(ckpt_fn, 'rb') as ckpt_file:
                stats, move_list = pickle.load(ckpt_file)
        else:
            self.bot.clear_board()
            self.bot.go_to_position()
            stats, move_list = self.bot.analyze()
            with open(ckpt_fn, 'wb') as ckpt_file:
                pickle.dump((stats, move_list), ckpt_file)

        return stats, move_list

    def prepare(self):
        """ Stores moves to analyze and wipes comments if needed"""
        base_hash = hashlib.md5(str(self.sgf_data).encode()).hexdigest()
        self.base_dir = os.path.join(settings.CHECKPOINTS_DIR.format(self._bot_config), base_hash)
        os.makedirs(self.base_dir, exist_ok=True)

        move_num = -1

        while not self.cursor.atEnd:

            self.cursor.next()
            move_num += 1

            if CONFIG['move_from'] <= move_num + 1 <= CONFIG['move_till']:
                self.moves_to_analyze[move_num] = True

            node_comment = self.cursor.node.get('C')
            if node_comment and CONFIG['wipe_comments']:
                node_comment.data[0] = ""

    def analyze_main_line(self):
        logger.info("Started analyzing main line.")

        move_num = -1
        prev_stats = {}
        prev_move_list = []
        has_prev = False
        previous_player = None

        logger.info(f"Executing analysis for %d moves", len(self.moves_to_analyze))
        moves_count = 0
        self.cursor.reset()
        self.bot = self.factory()
        self.bot.time_per_move = CONFIG['analyze_time']
        self.bot.start()
        # analyze main line, without variations
        while not self.cursor.atEnd:
            self.cursor.next()
            move_num += 1
            this_move = self.add_moves_to_bot()

            current_player = 'black' if 'W' in self.cursor.node else 'white'

            if previous_player == current_player:
                raise BotException('Two consecutive moves.')

            if move_num in self.moves_to_analyze:
                stats, move_list = self.do_analyze()

                # Here we store ALL statistics
                self.all_stats[move_num] = stats
                self.all_move_lists[move_num] = move_list

                if move_list and 'winrate' in move_list[0]:
                    self.best_moves[move_num] = move_list[0]

                delta = 0.0

                if 'winrate' in stats and (move_num - 1) in self.best_moves:
                    if this_move != self.best_moves[move_num - 1]['pos']:
                        delta = stats['winrate'] - self.best_moves[move_num - 1]['winrate']
                        delta = min(0.0, (-delta if self.bot.whose_turn() == "black" else delta))

                    if -delta > CONFIG['analyze_threshold']:
                        (delta_comment, delta_lb_values) = annotations.format_delta_info(delta, this_move,
                                                                                         self.board_size)
                        annotations.annotate_sgf(self.cursor, delta_comment, delta_lb_values, [])

                if has_prev and delta <= -CONFIG['variations_threshold']:
                    self.moves_to_variations[move_num - 1] = True

                if -delta > CONFIG['analyze_threshold']:
                    logger.warning("Move %d: %s %s is a mistake (winrate dropped by %.2f%%)", move_num + 1,
                                   previous_player, convert_position(self.board_size, this_move), -delta * 100)

                next_game_move = self.next_move_pos()

                annotations.annotate_sgf(self.cursor,
                                         annotations.format_winrate(stats, move_list, self.board_size, next_game_move),
                                         [], [])

                if has_prev and ((move_num - 1) in self.moves_to_analyze and -delta > CONFIG['analyze_threshold'] or (
                        move_num - 1) in self.moves_to_variations):
                    (analysis_comment, lb_values, tr_values) = annotations.format_analysis(
                        prev_stats, filter_move_list(prev_move_list), this_move, self.board_size)
                    self.cursor.previous()
                    # adding comment to sgf with suggested alternative variations
                    annotations.annotate_sgf(self.cursor, analysis_comment, lb_values, tr_values)
                    self.cursor.next()

                prev_stats = stats
                prev_move_list = move_list
                has_prev = True

                self.save_to_file()
                self.graph_winrates()

                if 'winrate' in stats and 1 - CONFIG['stop_on_winrate'] > stats['winrate'] > CONFIG['stop_on_winrate']:
                    break

                moves_count += 1
                logger.info("Analysis done for %d/%d move.", moves_count, len(self.moves_to_analyze))
            else:
                prev_stats = {}
                prev_move_list = []
                has_prev = False

            previous_player = current_player

        logger.info("Finished analyzing main line.")

    def do_variations(self, move_num):
        stats = self.all_stats[move_num]
        move_list = filter_move_list(self.all_move_lists[move_num])
        game_move = self.next_move_pos()

        rootcolor = self.bot.whose_turn()
        leaves = []
        tree = {"children": [],
                "is_root": True,
                "history": [],
                "explored": False,
                "stats": stats,
                "move_list": move_list,
                "color": rootcolor}

        def expand(node, stats, move_list):
            assert node["color"] in ['white', 'black']

            for move in move_list:
                # Don't expand on the actual game line as a variation!
                if node["is_root"] and move["pos"] == game_move:
                    continue

                subhistory = node["history"][:]
                subhistory.append(move["pos"])
                clr = "white" if node["color"] == "black" else "black"
                child = {"children": [],
                         "is_root": False,
                         "history": subhistory,
                         "explored": False,
                         "stats": {},
                         "move_list": [],
                         "color": clr}
                node["children"].append(child)
                leaves.append(child)

            node["stats"] = stats
            node["move_list"] = move_list
            node["explored"] = True

            for leaf_idx in range(len(leaves)):
                if leaves[leaf_idx] is node:
                    del leaves[leaf_idx]
                    break

        def analyze_and_expand(node):

            for mv in node["history"]:
                self.bot.add_move_to_history(self.bot.whose_turn(), mv)
            stats, move_list = self.do_analyze()

            expand(node, stats, filter_move_list(move_list))
            self.bot.pop_move_from_history(len(node['history']))

        expand(tree, stats, move_list)

        for i in range(CONFIG['variations_depth']):
            if len(leaves) > 0:
                for leaf in leaves:
                    if not len(leaf['history']) > CONFIG['variations_depth']:
                        analyze_and_expand(leaf)

        def advance(color, mv):
            found_child_idx = None
            clr = 'W' if color == 'white' else 'B'

            for j in range(len(self.cursor.children)):
                if clr in self.cursor.children[j].keys() and self.cursor.children[j][clr].data[0] == mv:
                    found_child_idx = j

            if found_child_idx is not None:
                self.cursor.next(found_child_idx)
            else:
                nnode = Node()
                nnode.add_property(Property(clr, [mv]))
                self.cursor.append_node(nnode)
                self.cursor.next(len(self.cursor.children) - 1)

        def record(node):
            if not node["is_root"]:
                annotations.annotate_sgf(self.cursor,
                                         annotations.format_winrate(node["stats"], node["move_list"],
                                                                    self.board_size, None),
                                         [], [])
                move_list_to_display = []

                # Only display info for the principal variation or for lines that have been explored.
                for i in range(len(node["children"])):
                    child = node["children"][i]

                    if child is not None and (i == 0 or child["explored"]):
                        move_list_to_display.append(node["move_list"][i])

                (analysis_comment, lb_values, tr_values) = annotations.format_analysis(node["stats"],
                                                                                       move_list_to_display,
                                                                                       None, self.board_size)
                annotations.annotate_sgf(self.cursor, analysis_comment, lb_values, tr_values)

            for i in range(len(node["children"])):
                child = node["children"][i]

                if child is not None:
                    if child["explored"]:
                        advance(node["color"], child["history"][-1])
                        record(child)
                        self.cursor.previous()
                    # Only show variations for the principal line, to prevent info overload
                    elif i == 0:
                        pv = node["move_list"][i]["pv"]
                        color = node["color"]

                        if CONFIG['num_to_show']:
                            num_to_show = min(len(pv), CONFIG['num_to_show'])
                        else:
                            num_to_show = len(pv)

                        for k in range(int(num_to_show)):
                            advance(color, pv[k])
                            color = 'black' if color == 'white' else 'white'

                        for k in range(int(num_to_show)):
                            self.cursor.previous()

        record(tree)

    def analyze_variations(self):
        logger.info("Started deep analysis of mistakes.")

        move_num = -1
        self.cursor.reset()
        self.bot.reset()
        self.bot.time_per_move = CONFIG['variations_time']
        self.add_moves_to_bot()

        logger.info("Exploring variations for %d moves with %d depth.",
                    len(self.moves_to_variations),
                    CONFIG['variations_depth'])
        moves_count = 0
        while not self.cursor.atEnd:
            self.cursor.next()
            move_num += 1
            self.add_moves_to_bot()

            if move_num not in self.moves_to_variations:
                continue

            stats, move_list = self.all_stats[move_num], self.all_move_lists[move_num]

            if 'bookmoves' in stats or len(move_list) <= 0:
                continue

            self.do_variations(move_num)
            moves_count += 1
            logger.info("Analyzed %d/%d mistakes.", moves_count, len(self.moves_to_variations))

            self.save_to_file()

        logger.info("Finished deep analysis of mistakes.")

    def run(self):
        logger.info("Started analyzing file: %s", os.path.basename(self._path_to_sgf))

        self.parse_sgf_file()
        self.cursor = self.sgf_data.cursor()

        try:
            self.prepare()
            self.analyze_main_line()
            self.analyze_variations()
        except:
            logger.exception("Exception during analysis.")
        finally:
            self.bot.stop()

        logger.info("Finished analyzing file: %s", os.path.basename(self._path_to_sgf))


if __name__ == '__main__':
    root = tk.Tk()
    root.withdraw()

    cmd_args = parse_cmd_line()
    games = filedialog.askopenfilenames()

    logger.info('%s games selected for analysis.', len(games))

    queue = []
    for game in games:
        queue.append(BotAnalyzer(game, cmd_args.bot))

    for game in queue:
        game.run()

    logger.info('Analysis done for %s sgf-files.', len(games))
