from sgftools import annotations, sgflib
from .analyze import do_analyze


# move_list is from a call to do_analyze
# Iteratively expands a tree of moves by expanding on the leaf with the highest "probability of reaching".
def do_variations(cursor, leela, stats, move_list, board_size, game_move, base_dir, args):
    rootcolor = leela.whose_turn()
    leaves = []
    tree = {"children": [],
            "is_root": True,
            "history": [],
            "explored": False,
            "stats": stats,
            "move_list": move_list,
            "color": rootcolor}

    def expand(node, stats, move_list):
        assert node["color"] in ['white', 'black']

        for move in move_list:
            # Don't expand on the actual game line as a variation!
            if node["is_root"] and move["pos"] == game_move:
                node["children"].append(None)
                continue

            subhistory = node["history"][:]
            subhistory.append(move["pos"])
            clr = "white" if node["color"] == "black" else "black"
            child = {"children": [],
                     "is_root": False,
                     "history": subhistory,
                     "explored": False,
                     "stats": {},
                     "move_list": [],
                     "color": clr}
            node["children"].append(child)
            leaves.append(child)

        node["stats"] = stats
        node["move_list"] = move_list
        node["explored"] = True

        for leaf_idx in range(len(leaves)):
            if leaves[leaf_idx] is node:
                del leaves[leaf_idx]
                break

    def analyze_and_expand(node):
        for mv in node["history"]:
            leela.add_move(leela.whose_turn(), mv)
        stats, move_list, skipped = do_analyze(leela, base_dir, args.verbosity, args.variations_time)
        expand(node, stats, move_list)
        leela.pop_move(len(node['history']))

    expand(tree, stats, move_list)

    for i in range(args.variations_depth):
        if len(leaves) > 0:
            for leaf in leaves:
                    analyze_and_expand(leaf)

    def advance(cursor, color, mv):
        found_child_idx = None
        clr = 'W' if color == 'white' else 'B'

        for j in range(len(cursor.children)):
            if clr in cursor.children[j].keys() and cursor.children[j][clr].data[0] == mv:
                found_child_idx = j

        if found_child_idx is not None:
            cursor.next(found_child_idx)
        else:
            nnode = sgflib.Node()
            nnode.add_property(sgflib.Property(clr, [mv]))
            cursor.append_node(nnode)
            cursor.next(len(cursor.children) - 1)

    def record(node):
        if not node["is_root"]:
            annotations.annotate_sgf(cursor,
                                     annotations.format_winrate(node["stats"], node["move_list"], board_size, None),
                                     [], [])
            move_list_to_display = []

            # Only display info for the principal variation or for lines that have been explored.
            for i in range(len(node["children"])):
                child = node["children"][i]

                if child is not None and (i == 0 or child["explored"]):
                    move_list_to_display.append(node["move_list"][i])

            (analysis_comment, lb_values, tr_values) = annotations.format_analysis(node["stats"], move_list_to_display,
                                                                                   None)
            annotations.annotate_sgf(cursor, analysis_comment, lb_values, tr_values)

        for i in range(len(node["children"])):
            child = node["children"][i]

            if child is not None:
                if child["explored"]:
                    advance(cursor, node["color"], child["history"][-1])
                    record(child)
                    cursor.previous()
                # Only show variations for the principal line, to prevent info overload
                elif i == 0:
                    pv = node["move_list"][i]["pv"]
                    color = node["color"]

                    if args.num_to_show:
                        num_to_show = min(len(pv), args.num_to_show)
                    else:
                        num_to_show = len(pv)

                    for k in range(int(num_to_show)):
                        advance(cursor, color, pv[k])
                        color = 'black' if color == 'white' else 'white'

                    for k in range(int(num_to_show)):
                        cursor.previous()

    record(tree)
