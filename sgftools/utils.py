import math
import sys
import os

import numpy as np
import matplotlib.pyplot as plt

SGF_COORD = 'abcdefghijklmnopqrstuvwxy'
BOARD_COORD = 'abcdefghjklmnopqrstuvwxyz'  # without "i"


def save_to_file(sgf_fn, content):
    path_to_save = "_analyzed".join(os.path.splitext(sgf_fn))
    with open(path_to_save, mode='w', encoding='utf-8') as f:
        f.write(str(content))


def convert_position(board_size, pos):
    """
    Convert SGF coordinates to board position coordinates
    Example aa -> A1, qq -> P15
    """
    x = BOARD_COORD[SGF_COORD.index(pos[0])].upper()
    y = board_size - SGF_COORD.index(pos[1])

    return '%s%d' % (x, y)


def parse_position(board_size, pos):
    """
    Convert board position coordinates to SGF coordinates
    Example A1 -> aa, P15 -> qq
    :return: string
    """
    # Pass moves are the empty string in sgf files
    if pos == "pass":
        return ""

    x = BOARD_COORD.index(pos[0].lower())
    y = board_size - int(pos[1:])

    return "%s%s" % (SGF_COORD[x], SGF_COORD[y])


def graph_winrates(winrates, sgf_fn):
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
    file_name = f"{os.path.splitext(sgf_fn)[0]}_graph.pdf"
    plt.savefig(file_name, dpi=200, format='pdf', bbox_inches='tight')


def winrate_transformer(stdev, verbosity):
    """
    Make a function that applies a transform to the winrate that stretches out the middle
    range and squashes the extreme ranges, to make it a more linear function and suppress
    Leela's suggestions in won/lost games.
    Currently, the CDF of the probability distribution from 0 to 1 given by x^k * (1-x)^k,
    where k is set to be the value such that the stdev of the distribution is stdev.
    :return: winrate
    """

    def variance(k):
        """
        Variance of the distribution =
        = The integral from 0 to 1 of (x-0.5)^2 x^k (1-x)^k dx
        = (via integration by parts)  (k+2)!k! / (2k+3)! - (k+1)!k! / (2k+2)! + (1/4) * k!^2 / (2k+1)!

        Normalize probability by dividing by the integral from 0 to 1 of x^k (1-x)^k dx: k!^2 / (2k+1)!
        And we get:	 (k+1) * (k+2) / (2k+2) / (2k+3) - (k+1) / (2k+2) + (1/4)
        :param k: 0 <= k <= 1
        """
        k = float(k)
        return 0.25 - (k ** 2 + 2 * k + 1) / (2 * k ** 2 + 5 * k + 3) / 2

    def find_k(lower, upper):
        """
        Binary search to find the appropriate k
        """
        while True:
            mid = 0.5 * (lower + upper)
            if mid == lower or mid == upper or lower >= upper:
                return mid
            var = variance(mid)
            if var < stdev * stdev:
                upper = mid
            else:
                lower = mid

    if stdev * stdev <= 1e-10:
        raise ValueError("Stdev too small, please choose a more reasonable value")

    # Repeated doubling to find an upper bound big enough
    upper = 1
    while variance(upper) > stdev * stdev:
        upper = upper * 2

    k = find_k(0, upper)

    if verbosity > 2:
        print("Using k = %f, stdev = %f" % (k, math.sqrt(variance(k))), file=sys.stderr)

    def unnormpdf(x):
        """
        Unnormalize probability density function
        """
        if x <= 0 or x >= 1:
            return 0
        a = math.log(x)
        b = math.log(1 - x)
        logprob = a * k + b * k
        # Constant scaling so we don't overflow floats with crazy values
        logprob = logprob - 2 * k * math.log(0.5)
        return math.exp(logprob)

    # Precompute a big array to approximate the CDF
    n = 100000
    lookup = [unnormpdf(float(x) / float(n)) for x in range(n + 1)]
    cum = 0

    for i in range(n + 1):
        cum += lookup[i]
        lookup[i] = cum

    for i in range(n + 1):
        lookup[i] = lookup[i] / lookup[n]

    def cdf(x):
        """
        Cumulative distribution function
        """
        i = int(math.floor(x * n))
        if i >= n or i < 0:
            return x
        excess = x * n - i
        return lookup[i] + excess * (lookup[i + 1] - lookup[i])

    return lambda x: cdf(x)
