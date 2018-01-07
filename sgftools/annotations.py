from sgflib import Property, Node
from sgftools.utils import convert_position, is_pass


def format_winrate(stats, move_list, board_size, next_game_move):
    comment = ""
    if 'winrate' in stats:
        comment += "Overall black win%%: %.2f%%\n" % (stats['winrate'] * 100)
    else:
        comment += "Overall black win%: not computed (Leela still in opening book)\n"

    if len(move_list) > 0 and move_list[0]['pos'] != next_game_move:
        comment += "Leela's preferred next move: %s\n" % convert_position(board_size, move_list[0]['pos'])
    else:
        comment += "\n"

    return comment


def format_delta_info(delta, this_move, board_size):
    comment = ""
    LB_values = []
    if delta <= -0.2:
        comment += "=================================\n"
        comment += "Leela thinks %s is a big mistake!\n" % convert_position(board_size, this_move)
        comment += "Winning percentage drops by %.2f%%!\n" % (-delta * 100)
        comment += "=================================\n"
        if not is_pass(board_size, this_move):
            LB_values.append("%s:%s" % (this_move, "?"))
    elif delta <= -0.1:
        comment += "=================================\n"
        comment += "Leela thinks %s is a mistake!\n" % convert_position(board_size, this_move)
        comment += "Winning percentage drops by %.2f%%\n" % (-delta * 100)
        comment += "=================================\n"
        if not is_pass(board_size, this_move):
            LB_values.append("%s:%s" % (this_move, "?"))
    elif delta <= -0.05:
        comment += "=================================\n"
        comment += "Leela thinks %s is not the best choice.\n" % convert_position(board_size, this_move)
        comment += "Winning percentage drops by %.2f%%\n" % (-delta * 100)
        comment += "=================================\n"
        if not is_pass(board_size, this_move):
            LB_values.append("%s:%s" % (this_move, "?"))
    elif delta <= -0.025:
        comment += "=================================\n"
        comment += "Leela slightly dislikes %s.\n" % convert_position(board_size, this_move)
        comment += "=================================\n"

    comment += "\n"
    return comment, LB_values


def flip_winrate(wr, color):
    return (1.0 - wr) if color == "white" else wr


def format_analysis(stats, move_list, this_move, board_size):
    abet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    comment = ""
    if 'bookmoves' in stats:
        comment += "==========================\n"
        comment += "Considered %d/%d bookmoves\n" % (stats['bookmoves'], stats['positions'])
    else:
        comment += "==========================\n"
        comment += "Visited %d nodes\n" % (stats['visits'])
        comment += "\n"

        for move_label, move in list(zip(abet, move_list)):
            comment += "%s -> Win%%: %.2f%% (%d visits) \n" \
                       % (move_label, flip_winrate(move['winrate'], move['color']) * 100, move['visits'])

    # Check for pos being "" or "tt", values which indicate passes, and don't attempt to display markers for them
    LB_values = ["%s:%s" % (mv['pos'], L) for L, mv in zip(abet, move_list) if mv['pos'] != "" and mv['pos'] != "tt"]
    mvs = [mv['pos'] for mv in move_list]
    if this_move not in mvs and this_move is not None and not is_pass(board_size, this_move):
        TR_values = [this_move]
    else:
        TR_values = []
    return comment, LB_values, TR_values


def annotate_sgf(cursor, comment, LB_values, TR_values):
    c_node = cursor.node
    if 'C' in c_node:
        c_node['C'].data[0] += comment
    else:
        c_node.add_property(Property('C', [comment]))

    if len(LB_values) > 0:
        c_node.add_property(Property('LB', LB_values))

    if len(TR_values) > 0:
        c_node.add_property(Property('TR', TR_values))
