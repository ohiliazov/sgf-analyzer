class Collection:
    """
    An SGF collection: multiple 'GameTree''s.
    Instance attributes:
    - game_list : list of 'GameTree' -- One 'GameTree' per game.
    """

    def __init__(self, game_list=None):
        self.game_list = game_list or []

    def __str__(self):
        """ SGF representation. Separates game trees with a blank line."""
        return "\n\n".join([str(x) for x in self.game_list])

    def cursor(self, game_num=0):
        """ Returns a 'Cursor' object for navigation of the given 'GameTree'."""
        return Cursor(self.game_list[game_num])


class GameTree:
    """
    An SGF game tree: a game or variation.
    Instance attributes:
    - self.node_list: list of 'Node' -- game tree 'trunk'.
    - self.variations: list of 'GameTree' -- 0 or 2+ variations.
    'self.variations[0]' contains the actual game sequence.
    """
    MAX_LINE_LEN = 120

    def __init__(self, node_list=None, var_list=None):
        self.node_list = node_list or []
        self.var_list = var_list or []

    def __str__(self):
        """ SGF representation, with proper line breaks between nodes."""
        if len(self.node_list):
            s = "(" + str(self.node_list[0])  # append the first Node automatically
            l = len(s.split("\n")[-1])  # accounts for line breaks within Nodes
            for n in [str(x) for x in self.node_list[1:]]:
                if l + len(n.split("\n")[0]) > self.MAX_LINE_LEN:
                    s = s + "\n"
                s = s + n
                l = len(s.split("\n")[-1])
            return s + "\n".join([str(x) for x in [""] + self.var_list]) + ")"
        else:
            return ""  # empty GameTree illegal; "()" illegal


class Cursor:
    def __init__(self, game_tree):
        self.game_tree = game_tree
