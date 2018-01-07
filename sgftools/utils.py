import os

import numpy as np
import matplotlib.pyplot as plt
import re

SGF_COORD = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u',
             'v', 'w', 'x', 'y', 'z', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P',
             'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X']

BRD_COORD = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V',
             'W', 'X', 'Y', 'Z', 'AA', 'BB', 'CC', 'DD', 'EE', 'FF', 'GG', 'HH', 'JJ', 'KK', 'LL', 'MM', 'NN', 'OO',
             'PP', 'QQ', 'RR', 'SS', 'TT', 'UU', 'VV', 'WW', 'XX', 'YY', 'ZZ']


class PointValueError(Exception):
    """Raised by [convert_position]"""
    pass


def is_pass(board_size, pos):
    return True if pos in ["", "pass"] or (pos == "tt" and board_size <= 19) else False


def convert_position(board_size, coord):
    """
    Convert SGF coordinates to board position coordinates
    Example aa -> A1, qq -> P15"""

    if coord == "" or (coord == "tt" and board_size <= 19):
        return "pass"

    if coord[0] not in SGF_COORD or board_size <= SGF_COORD.index(coord[0]) or board_size <= SGF_COORD.index(coord[1]):
        raise PointValueError(f'"{coord}" is not a valid point for board size = {board_size}.')

    x = BRD_COORD[SGF_COORD.index(coord[0])]
    y = board_size - SGF_COORD.index(coord[1])

    return f"{x}{y}"


def parse_position(board_size, pos):
    """
    Convert board position coordinates to SGF coordinates
    Example A1 -> aa, P15 -> qq
    """
    # Pass moves are the empty string in sgf files
    if pos == "pass":
        return ""

    match = re.match(r"([a-zA-Z]+){1,2}([0-9]+){1,2}", pos)
    if match and BRD_COORD.index(match.group(1)) < board_size and int(match.group(2)) <= board_size:
        x = SGF_COORD[BRD_COORD.index(match.group(1))]
        y = SGF_COORD[board_size - int(match.group(2))]
        return f"{x}{y}"
    else:
        raise PointValueError(f'"{pos} is not a valid point for board size = {board_size}')


def save_to_file(sgf_fn, content):
    path_to_save = "_analyzed".join(os.path.splitext(sgf_fn))
    with open(path_to_save, mode='w', encoding='utf-8') as f:
        f.write(str(content))


def graph_winrates(winrates, sgf_fn):
    x = []
    y = []
    for move_num in sorted(winrates.keys()):
        if 'winrate' not in winrates[move_num]:
            continue
        x.append(move_num)
        y.append(winrates[move_num]['winrate'])

    plt.figure()

    # fill graph with horizontal coordinate lines, step 0.25
    for xc in np.arange(0, 1, 0.025):
        plt.axhline(xc, 0, max(winrates.keys()), linewidth=0.04, color='0.7')

    # add single central horizontal line
    plt.axhline(0.50, 0, max(winrates.keys()), linewidth=0.3, color='0.2')

    # main graph of win rate changes
    plt.plot(x, y, color='#ff0000', marker='.', markersize=2.5, linewidth=0.6)

    # set range limits for x and y axes
    plt.xlim(0, max(winrates.keys()))
    plt.ylim(0, 1)

    # set size of numbers on axes
    plt.yticks(np.arange(0, 1.05, 0.05), fontsize=6)
    plt.yticks(fontsize=6)

    # add labels to axes
    plt.xlabel("Move Number", fontsize=10)
    plt.ylabel("Win Rate", fontsize=12)

    # in this script for pdf it use the same file name as provided sgf file to avoid extra parameters
    file_name = f"{os.path.splitext(sgf_fn)[0]}_graph.pdf"
    plt.savefig(file_name, dpi=200, format='pdf', bbox_inches='tight')
