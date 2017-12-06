"""
A dummy version of new annotations tool
"""


def comment_winrate(stats, move_list, board_size, next_move):
    pass


def comment_delta(this_move, delta, board_size):
    pass


def comment_analysis(stats, move_list, this_move):
    pass


def comment_move(comment_type, stats=None, move_list=None, this_move=None, next_move=None, delta=None, board_size=None):
    """Annotates SGF"""
    if comment_type == 'winrate':
        return comment_winrate(stats, move_list, board_size, next_move)

    elif comment_type == 'delta':
        return comment_delta(this_move, delta, board_size)

    elif comment_type == 'analysis':
        return comment_analysis(stats, move_list, this_move)
