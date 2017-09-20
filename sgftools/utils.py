import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

SGF_COORD = 'abcdefghijklmnopqrstuvwxy'
BOARD_COORD = 'abcdefghjklmnopqrstuvwxyz'  # without "i"


def write_to_file(filename, mode, content):
    """
    Writes sgf to file
    :param filename: 
    :param mode: 
    :param content: 
    :return: 
    """
    with open(filename, mode, encoding='utf-8') as f:
        f.write(str(content))


def convert_position(board_size, pos):
    """
    Convert SGF coordinates to board position coordinates
    Example aa -> a1, qq -> p15
    :param pos: string
    :param board_size: int

    :return: string
    """
    x = BOARD_COORD[SGF_COORD.index(pos[0])]
    y = board_size - SGF_COORD.index(pos[1])

    return '%s%d' % (x, y)


def parse_position(board_size, pos):
    """
    Convert board position coordinates to SGF coordinates
    Example A1 -> aa, P15 -> qq
    :param pos: string
    :param board_size: int

    :return: string
    """
    # Pass moves are the empty string in sgf files
    if pos == "pass":
        return ""

    x = BOARD_COORD.index(pos[0].lower())
    y = board_size - int(pos[1:])

    return "%s%s" % (SGF_COORD[x], SGF_COORD[y])


def graph_winrates(winrates, file_to_save):
    mpl.use('Agg')

    x = []
    y = []

    for move_num in sorted(winrates.keys()):
        pl, wr = winrates[move_num]

        x.append(move_num)
        y.append(wr)

    plt.figure(1)

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
    file_name = file_to_save.split('.')[0] + '_graph.pdf'
    plt.savefig(file_name, dpi=200, format='pdf', bbox_inches='tight')
