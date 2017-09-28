from sgftools.sgflib import Property, Node


def insert_sequence(cursor, seq, data=None, callback=None):
    if data is None:
        data = [0] * len(seq)

    for (color, move), elem in list(zip(seq, data)):
        n_node = Node()
        assert color in ['white', 'black']

        if color == 'white':
            color = 'W'
        else:
            color = 'B'

        n_node.add_property(Property(color, [move]))
        cursor.append_node(n_node)
        cursor.next(len(cursor.children) - 1)

        if callback is not None:
            if type(elem) in [list, tuple]:
                elem = list(elem)
            else:
                elem = [elem]
            callback(*tuple([cursor] + elem))

    for i in range(len(seq)):
        cursor.previous()


def format_variation(cursor, seq):
    move_seq = [(color, mv) for color, mv, _stats, _mv_list in seq]
    move_data = [('black' if color == 'white' else 'white', stats, mv_list) for color, _mv, stats, mv_list in seq]
    insert_sequence(cursor, move_seq, move_data, format_analysis)


def pos_is_pass(pos):
    if pos == "" or pos == "tt":
        return True
    return False


def format_pos(pos, board_size):
    # In an sgf file, passes are the empty string or tt
    if pos_is_pass(pos):
        return "pass"
    if len(pos) != 2:
        return pos
    return "ABCDEFGHJKLMNOPQRSTUVXYZ"[ord(pos[0]) - ord('a')] + str(board_size - (ord(pos[1]) - ord('a')))


def format_winrate(stats, move_list, board_size, next_game_move):
    comment = ""
    if 'winrate' in stats:
        comment += "Overall black win%%: %.2f%%\n" % (stats['winrate'] * 100)
    else:
        comment += "Overall black win%: not computed (Leela still in opening book)\n"

    # Comment if leela preffered another next move
    if len(move_list) > 0 and move_list[0]['pos'] != next_game_move:
        comment += "Leela's preferred next move: %s\n" % format_pos(move_list[0]['pos'], board_size)
    else:
        comment += "\n"

    return comment


def format_delta_info(delta, trans_delta, stats, this_move, board_size):
    comment = ""
    LB_values = []
    if trans_delta <= -0.2:
        comment += "=================================\n"
        comment += "Leela thinks %s is a big mistake!\n" % format_pos(this_move, board_size)
        comment += "Winning percentage drops by %.2f%%!\n" % (-delta * 100)
        comment += "=================================\n"
        if not pos_is_pass(this_move):
            LB_values.append("%s:%s" % (this_move, "?"))
    elif trans_delta <= -0.1:
        comment += "=================================\n"
        comment += "Leela thinks %s is a mistake!\n" % format_pos(this_move, board_size)
        comment += "Winning percentage drops by %.2f%%\n" % (-delta * 100)
        comment += "=================================\n"
        if not pos_is_pass(this_move):
            LB_values.append("%s:%s" % (this_move, "?"))
    elif trans_delta <= -0.05:
        comment += "=================================\n"
        comment += "Leela thinks %s is not the best choice.\n" % format_pos(this_move, board_size)
        comment += "Winning percentage drops by %.2f%%\n" % (-delta * 100)
        comment += "=================================\n"
        if not pos_is_pass(this_move):
            LB_values.append("%s:%s" % (this_move, "?"))
    elif trans_delta <= -0.025:
        comment += "=================================\n"
        comment += "Leela slightly dislikes %s.\n" % format_pos(this_move, board_size)
        comment += "=================================\n"

    comment += "\n"
    return comment, LB_values


def flip_winrate(wr, color):
    return (1.0 - wr) if color == "white" else wr


def format_analysis(stats, move_list, this_move):
    """
    Make comment with analysis information, such as number of visits and alternate moves winrates
    :return: string
    """
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

    # Mark labels and skip passes
    label_values = []
    for move_label, move in zip(abet, move_list):
        if move['pos'] not in ["", "tt"]:
            label_values.append("%s:%s" % (move['pos'], move_label))

    suggested_moves = [move['pos'] for move in move_list]

    # Mark triangles
    if this_move and this_move not in suggested_moves and not pos_is_pass(this_move):
        triangle_values = [this_move]
    else:
        triangle_values = None

    return comment, label_values, triangle_values


def annotate_sgf(cursor, comment, labels_values=None, triangle_values=None):
    """
    Add comment, labels and triangles to node
    """
    node_comment = cursor.node.get('C')
    node_labels = cursor.node.get('LB')
    node_triangles = cursor.node.get('TR')

    # Add comment to existing property or create
    if node_comment:
        node_comment.data[0] += comment
    else:
        cursor.node.add_property(Property('C', [comment]))

    # Add labels
    if labels_values:
        if node_labels:
            node_labels.data = labels_values
        else:
            cursor.node.add_property(Property('LB', labels_values))

    # Add triangles
    if triangle_values:
        if node_triangles:
            node_triangles.data = triangle_values
        else:
            cursor.node.add_property(Property('TR', triangle_values))


def self_test_1():
    print(pos_is_pass(""), pos_is_pass("tt"), pos_is_pass('ab'))
    print(format_pos("aa", 19), format_pos("jj", 19), format_pos("ss", 19))


if __name__ == '__main__':
    self_test_1()
