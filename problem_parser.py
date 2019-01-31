import json
import os
import re
import sys

EMPTY = 0
BLACK = 1
WHITE = 2
OFF_BOARD = 4


def get_sgf_pos(x, y):
    return chr(y + 96) + chr(x + 96)


def to_number_array(state: str):
    numbers = []
    for i in state:
        c = ord(i) - 64
        d = c % 3
        numbers.append(d)
        c = (c - d) // 3
        d = c % 3
        numbers.append(d)
        c = (c - d) // 3
        d = c % 3
        numbers.append(d)
    return numbers


def to_stone_array(numbers: list, board_size: int = 19):
    stones = []
    i = 0
    for x in range(board_size + 2):
        for y in range(board_size + 2):
            if x == 0 or x == board_size + 1 or y == 0 or y == board_size + 1:
                stones.append(OFF_BOARD)
            else:
                stones.append(numbers[i])
                i += 1

    return stones


def to_color_array(stones: list, board_size: int = 19):
    black, white = [], []
    for x in range(board_size + 2):
        line = stones[(board_size + 2) * x:(board_size + 2) * (x + 1)]

        for y in range(board_size + 2):
            coord = (x, y)
            pos = line[y]
            if pos == BLACK:
                black.append(get_sgf_pos(*coord))
            elif pos == WHITE:
                white.append(get_sgf_pos(*coord))

    return black, white


def make_sgf(black: list = None, white: list = None, lm: str = None, va: list = None, current: str = 'B',
             wr: list = None):
    res = '(;'

    if black:
        res += '\nAB'

        for b in black:
            res += f'[{b}]'

    if white:
        res += '\nAW'

        for w in white:
            res += f'[{w}]'

    if lm:
        res += f'\nTR[{lm}]'

    if wr:
        res += f'C[Best play: {wr[0]}%\n' \
                 f'Real play: {wr[1]}%]'
    for v in va:
        pl = current
        res += '\n('

        for i in range(0, len(v), 2):
            mv = v[i:i + 2]
            res += f';{pl}[{mv}]'

            pl = 'W' if pl == 'B' else 'B'

        res += ')'
    res += '\n)'
    return res


def parse_html(text: str):
    problems = re.search(r'(?<=LoadProblems\()[\w\W]+(?=\))', text).group()

    res = re.sub(r'([\{\s,])(\w+)(:)', r'\1"\2"\3', problems)

    return json.loads(res.replace('\t', '').replace('\n', '').replace("'", '"'))


if __name__ == '__main__':
    if len(sys.argv[1]) < 2:
        exit('Please provide path to file.')

    if not os.path.exists(sys.argv[1]):
        exit('File does not exist.')

    with open(sys.argv[1]) as f:
        w = f.read()

    problems = parse_html(w)

    for p in problems:
        sz = p['sz']
        lm = p['lm']
        va = p['va']
        cl = p['cl']
        wr = p['wr']
        b, w = to_color_array(to_stone_array(to_number_array(p['st']), sz))

        sgf = make_sgf(b, w, lm, va, cl, wr)

        with open(p["id"] + '.sgf', 'w+') as f:
            f.write(sgf)
