
SGF_COORD = 'abcdefghijklmnopqrstuvwxy'
BOARD_COORD = 'abcdefghjklmnopqrstuvwxyz'  # without "i"


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

