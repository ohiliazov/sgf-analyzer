from string import ascii_uppercase
from .sgflib import Property
from .utils import convert_position, is_pass


def format_winrate(stats, move_list, board_size, next_game_move):
    winrate = stats["winrate"]
    comment = f"Overall black win%%: {winrate:.2%}\n"

    if move_list and move_list[0]["pos"] != next_game_move:
        next_pos = convert_position(board_size, move_list[0]["pos"])
        comment += f"SAI prefers next move: {next_pos}\n"

    return comment


def format_delta_info(delta, this_move, board_size):
    if delta >= -0.025:
        return "\n", []

    pos = convert_position(board_size, this_move)
    lb_values = [f"{this_move}:?"]

    if delta <= -0.2:
        severity = "a big mistake"
    elif delta <= -0.1:
        severity = "a mistake"
    elif delta <= -0.05:
        severity = "not the best choice"
    else:
        severity = "slightly disadvantageous"

    comment = (
        f"=================================\n"
        f"SAI thinks {pos} is {severity}.\n"
        f"Winning percentage drops by {-delta:.2%}.\n"
        f"=================================\n"
        f"\n"
    )

    return comment, lb_values


def flip_winrate(wr, color):
    return (1.0 - wr) if color == "white" else wr


def format_analysis(stats: dict, move_list: list[dict], this_move: str, board_size: int):
    visits = stats["visits"]

    comment = (
        f"==========================\n"
        f"Visited {visits} nodes\n"
        f"\n"
    )

    for move_label, move in zip(ascii_uppercase, move_list):
        move_winrate = flip_winrate(move["winrate"], move["color"])
        move_visits = move["visits"]
        comment += f"{move_label} -> {move_winrate:.2%} ({move_visits} visits)\n"

    # Check for pos being "" or "tt", values which indicate passes, and don't attempt to display markers for them
    lb_values = [
        f"{mv['pos']}:{L}"
        for L, mv in zip(ascii_uppercase, move_list)
        if not is_pass(board_size, mv["pos"])
    ]
    mvs = [mv['pos'] for mv in move_list]
    if this_move and this_move not in mvs and not is_pass(board_size, this_move):
        tr_values = [this_move]
    else:
        tr_values = []
    return comment, lb_values, tr_values


def annotate_sgf(cursor, comment: str, lb_values: list[str], tr_values: list[str]):
    c_node = cursor.node

    if comment:
        if 'C' in c_node:
            c_node['C'].data[0] += comment
        else:
            c_node.add_property(Property('C', [comment]))

    if lb_values:
        if 'LB' in c_node:
            c_node['LB'].extend(lb_values)
        else:
            c_node.add_property(Property('LB', lb_values))

    if tr_values:
        if 'TR' in c_node:
            c_node['TR'].extend(tr_values)
        else:
            c_node.add_property(Property('TR', tr_values))
