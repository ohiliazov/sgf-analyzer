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


def is_pass(board_size, pos) -> bool:
    return bool(pos in ["", "pass"] or (pos == "tt" and board_size <= 19))


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