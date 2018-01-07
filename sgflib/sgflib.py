"""
=============================================
 Smart Game Format Parser Library: sgflib.py
=============================================
version 1.0 (2017-12-22)
Compatible with Python 3.6.3
"""

from collections import UserList, OrderedDict
import re

reGameTreeStart = re.compile(r'\s*\(')
reGameTreeEnd = re.compile(r'\s*\)')
reGameTreeNext = re.compile(r'\s*([;()])')
reNodeContents = re.compile(r'\s*([A-Za-z]+(?=\s*\[))')
rePropertyStart = re.compile(r'\s*\[')
rePropertyEnd = re.compile(r'\]')
reEscape = re.compile(r'\\')
reLineBreak = re.compile(r'\r\n?|\n\r?')  # CR, LF, CR/LF, LF/CR
reCharsToEscape = re.compile(r'[]\\]')  # characters that need to be \escaped


class EndOfDataParseError(Exception):
    """Raised by [SGFParser.parse_variations()], [SGFParser.parseNode()]."""
    pass


class GameTreeParseError(Exception):
    """Raised by [SGFParser.parse_game_tree()]."""
    pass


class NodePropertyParseError(Exception):
    """Raised by [SGFParser.parseNode()]."""
    pass


class PropertyValueParseError(Exception):
    """Raised by [SGFParser.parse_property_value()]."""
    pass


class GameTreeNavigationError(Exception):
    """Raised by [Cursor.next()]."""
    pass


class GameTreeEndError(Exception):
    """Raised by [Cursor.next()], [Cursor.previous()]."""
    pass


def _escape_text(text: str):
    """Adds backslash-escapes to property value characters that need them."""
    output = ""
    index = 0
    match = reCharsToEscape.search(text, index)

    while match:
        output = output + text[index:match.start()] + '\\' + text[match.start()]
        index = match.end()
        match = reCharsToEscape.search(text, index)

    output = output + text[index:]
    return output


def _convert_control_chars(text):
    """Converts control characters in [text] to spaces. Override for variant behaviour."""
    return text.translate(str.maketrans("\000\001\002\003\004\005\006\007\010\011\013\014\016\017\020"
                                        "\021\022\023\024\025\026\027\030\031\032\033\034\035\036\037", " " * 30))


class Collection(UserList):
    """
    An SGF collection: multiple [GameTree]. Instance attributes:
      - self[.data] : list of [GameTree] -- one [GameTree] per game."""

    def __str__(self):
        """SGF representation. Separates game trees with a blank line."""
        return "\n\n".join([str(x) for x in self])

    def cursor(self, index: int = 0):
        """Returns a 'Cursor' object for navigation of the given 'GameTree'."""
        return Cursor(self[index])


class Property(UserList):
    """
    An SGF property: a set of label and value(s). Instance attributes:
      - self[.data] : list of str -- property values.
      - self.label : string -- SGF standard property label."""

    def __init__(self, label: str, data: list):
        self.label = label
        self.data = data or ['']
        super().__init__(initlist=self.data)

    def __str__(self):
        return f"{self.label}[{']['.join([_escape_text(x) for x in self])}]"


class Node(OrderedDict):
    """
    An SGF node: a sequence of properties. Instance attributes:
      - self[.data] : ordered dictionary -- list of [Property.label:Property] mapping.

    Properties *must* be added using [self.add_property()]."""

    def __init__(self, pr_list: list = None):
        if pr_list is None:
            pr_list = []

        for prop in pr_list:  # type: Property
            self.add_property(prop)
        super().__init__()

    def __str__(self):
        """SGF representation of node. Has leading semicolon."""
        return f";{''.join([str(self[x]) for x in self])}"

    def add_property(self, prop: Property):
        return self.setdefault(prop.label, prop)


class GameTree(UserList):
    """
    An SGF game tree: a sequence of nodes. Instance attributes:
      - self[.data] : list of [Node] -- game tree 'trunk'.
      - self.variations : list of [GameTree] -- None or 2+ variations.

    [self.variations[0]] contains the main branch (sequence actually played)."""

    def __init__(self, n_list: list = None, variations: list = None):
        super().__init__(initlist=n_list)
        self.variations = variations or []

    def __str__(self):
        """SGF representation of game tree, with line breaks between nodes."""
        if len(self):
            return "(" + '\n'.join([str(x) for x in self + self.variations]) + ")"
        else:
            return ""

    def mainline(self):
        """Returns the main line of the game (variation A) as a [GameTree]."""
        if self.variations:
            return GameTree(self.data + self.variations[0].mainline())
        else:
            return self

    def cursor(self):
        """Returns a [Cursor] object for navigation of this [GameTree]."""
        return Cursor(self)

    def append_tree(self, variation: "GameTree", index: int):
        """Adds a variation to [GameTree]."""
        index += 1
        if index < len(self):
            subtree = GameTree(self.data[index:], self.variations)
            self.data = self.data[:index]
            self.variations = [subtree, variation]
        else:
            self.variations.append(variation)

    def append_node(self, node: Node):
        self.append(node)


class SGFParser:
    """
    Parser for SGF data. Creates a tree structure based on the SGF standard itself.
    [SGFParser.parse()] will return a [Collection] object for the entire data.

    Instance attributes:
      - self.data : string -- the complete SGF data instance.
      - self.data_len : integer -- length of [self.data].
      - self.index : integer -- current parsing position in [self.data]."""

    def __init__(self, data: str):
        self.data = data
        self.data_len = len(data)
        self.index = 0

    def _match_regex(self, regex):
        return regex.match(self.data, self.index)

    def _search_regex(self, regex):
        return regex.search(self.data, self.index)

    def parse(self):
        """Parses the SGF data stored in [self.data], and returns a [Collection]."""
        collection = Collection()
        while self.index < self.data_len:
            sgf_game = self.parse_one_game()
            if sgf_game:
                collection.append(sgf_game)
            else:
                break
        return collection

    def parse_one_game(self):
        """
        Parses one game from [self.data]. Returns a [GameTree] containing one game.
        Returns [None] if the end of [self.data] has been reached."""

        if self.index < self.data_len:
            match = self._match_regex(reGameTreeStart)
            if match:
                self.index = match.end()
                return self.parse_game_tree()
        return None

    def parse_game_tree(self):
        """
        Called when "(" encountered, ends when a matching ")" encountered.
        Parses and returns one [GameTree] from [self.data].
        Raises [GameTreeParseError] if a problem is encountered."""

        game_tree = GameTree()
        while self.index < self.data_len:
            match = self._match_regex(reGameTreeNext)
            if match:
                self.index = match.end()
                if match.group(1) == ";":  # Start of a node
                    if game_tree.variations:
                        raise GameTreeParseError("A node was encountered after a variation.")
                    game_tree.append(self.parse_node())
                elif match.group(1) == "(":  # Start of variation
                    game_tree.variations = self.parse_variations()
                else:  # End of GameTree ")"
                    return game_tree
            else:
                raise GameTreeParseError("Invalid SGF file format.")
        return game_tree

    def parse_variations(self):
        """
        Called when "(" encountered inside a [GameTree], ends when a non-matching ")" encountered.
        Returns a list of variation [GameTree].
        Raises [EndOfDataParseError] if the end of [self.data] is reached before the end of the enclosing [GameTree]."""

        variations = []
        while self.index < self.data_len:
            match = self._match_regex(reGameTreeEnd)  # Check for ")" at end of GameTree, but don't consume it
            if match:
                return variations
            game_tree = self.parse_game_tree()
            if game_tree:
                variations.append(game_tree)
            match = self._match_regex(reGameTreeStart)  # Check for next variation, and consume "("
            if match:
                self.index = match.end()
        raise EndOfDataParseError

    def parse_node(self):
        """
        Called when ";" encountered (& is consumed). Parses and returns one [Node], which can be empty.
        Raises [NodePropertyParseError] if no property values are extracted.
        Raises [EndOfDataParseError] if the end of [self.data] is reached before the end of the node (i.e., the start
        of the next node, the start of a variation, or the end of the enclosing game tree)."""

        node = Node()
        while self.index < self.data_len:
            match = self._match_regex(reNodeContents)
            if match:
                self.index = match.end()
                pv_list = self.parse_property_value()
                if pv_list:
                    prop = Property(match.group(1), pv_list)
                    node.add_property(prop)
                else:
                    raise NodePropertyParseError
            else:  # End of Node
                return node
        raise EndOfDataParseError

    def parse_property_value(self):
        """
        Called when "[" encountered (but not consumed), ends when the next property, node, or variation encountered.
        Parses and returns a list of property values. Raises [PropertyValueParseError] if there is a problem."""

        pv_list = []
        while self.index < self.data_len:
            match = self._match_regex(rePropertyStart)
            if match:
                self.index = match.end()
                value = ""
                match_end = self._search_regex(rePropertyEnd)
                match_escape = self._search_regex(reEscape)

                # Scan for escaped characters (using '\'), unescape them (remove linebreaks)
                while match_escape and match_end and (match_escape.end() < match_end.end()):
                    # Copy everything up to '\', but remove '\'
                    value = value + self.data[self.index:match_escape.start()]
                    match_break = reLineBreak.match(self.data, match_escape.end())
                    if match_break:
                        # Skip linebreak
                        self.index = match_break.end()
                    else:
                        # Copy escaped character and move to point after it
                        value = value + self.data[match_escape.end()]
                        self.index = match_escape.end() + 1
                    match_end = self._search_regex(rePropertyEnd)
                    match_escape = self._search_regex(reEscape)
                if match_end:
                    value = value + self.data[self.index:match_end.start()]
                    self.index = match_end.end()
                    pv_list.append(_convert_control_chars(value))
                else:
                    raise PropertyValueParseError
            else:  # End of Property
                break

        if len(pv_list):
            return pv_list
        else:
            raise PropertyValueParseError


class Cursor:
    """
    [GameTree] navigation tool. Instance attributes:
      - self.game : [GameTree] -- The root [GameTree].
      - self.game_tree : [GameTree] -- The current [GameTree].
      - self.node : [Node] -- The current Node.
      - self.node_num : integer -- The offset of [self.node] from the root of [self.game].
        The node_num of the root node is 0.
      - self.index : integer -- The offset of [self.node] within [self.game_tree].
      - self.stack : list of [GameTree] -- A record of [GameTree]s traversed.
      - self.children : list of [Node] -- All child nodes of the current node.
      - self.atEnd : boolean -- Flags if we are at the end of a branch.
      - self.atStart : boolean -- Flags if we are at the start of the game."""

    def __init__(self, game_tree: GameTree):
        self.game_tree = self.game = game_tree
        self.node_num = 0
        self.index = 0
        self.stack = []
        self.node = self.game_tree[self.index]
        self._set_children()
        self._set_flags()

    def reset(self):
        """Set 'Cursor' to point to the start of the root 'GameTree', 'self.game'."""
        self.__init__(self.game)

    def next(self, variation: int = 0):
        """
        Moves the [Cursor] to the next [Node] and returns it.
        Raises [GameTreeEndError] if the end of a branch is exceeded.
        Raises [GameTreeNavigationError] if a non-existent variation is accessed.
        Argument:
        - variation : integer, default 0 -- Variation number.
          Non-zero only valid at a branching, where variations exist."""
        if self.index + 1 < len(self.game_tree):  # more main line?
            if variation != 0:
                raise GameTreeNavigationError
            self.index = self.index + 1
        elif self.game_tree.variations:  # variations exist?
            if variation < len(self.game_tree.variations):
                self.stack.append(self.game_tree)
                self.game_tree = self.game_tree.variations[variation]
                self.index = 0
            else:
                raise GameTreeNavigationError
        else:
            raise GameTreeEndError
        self.node = self.game_tree[self.index]
        self.node_num = self.node_num + 1
        self._set_children()
        self._set_flags()
        return self.node

    def previous(self):
        """
        Moves the [Cursor] to the previous [Node] and returns it.
        Raises [GameTreeEndError] if the start of a branch is exceeded."""
        if self.index - 1 >= 0:  # more main line?
            self.index = self.index - 1
        elif self.stack:  # were we in a variation?
            self.game_tree = self.stack.pop()
            self.index = len(self.game_tree) - 1
        else:
            raise GameTreeEndError
        self.node = self.game_tree[self.index]
        self.node_num = self.node_num - 1
        self._set_children()
        self._set_flags()
        return self.node

    def append_node(self, node: Node):
        if self.index + 1 < len(self.game_tree) or self.game_tree.variations:
            self.game_tree.append_tree(GameTree([node]), self.index)
            self._set_children()
            self._set_flags()
        else:
            self.game_tree.append_node(node)
            self._set_children()
            self._set_flags()

    def _set_children(self):
        """Sets up [self.children]."""
        if self.index + 1 < len(self.game_tree):
            self.children = [self.game_tree[self.index + 1]]
        else:
            self.children = [x[0] for x in self.game_tree.variations]

    def _set_flags(self):
        """Sets up the flags [self.atEnd] and [self.atStart]."""
        self.atEnd = not self.game_tree.variations and (self.index + 1 == len(self.game_tree))
        self.atStart = not self.stack and (self.index == 0)
