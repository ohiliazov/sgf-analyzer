import re

from sgftools.typelib import List, Dictionary


# Parsing Exceptions

class EndOfDataParseError(Exception):
    """ Raised by 'SGFParser.parse_variations()', 'SGFParser.parseNode()'."""
    pass


class GameTreeParseError(Exception):
    """ Raised by 'SGFParser.parse_game_tree()'."""
    pass


class NodePropertyParseError(Exception):
    """ Raised by 'SGFParser.parseNode()'."""
    pass


class PropertyValueParseError(Exception):
    """ Raised by 'SGFParser.parse_property_value()'."""
    pass


# Tree Construction Exceptions

class DirectAccessError(Exception):
    """ Raised by 'Node.__setitem__()', 'Node.update()'."""
    pass


class DuplicatePropertyError(Exception):
    """ Raised by 'Node.add_property()'."""
    pass


# Tree Navigation Exceptions
class GameTreeNavigationError(Exception):
    """ Raised by 'Cursor.next()'."""
    pass


class GameTreeEndError(Exception):
    """ Raised by 'Cursor.next()', 'Cursor.previous()'."""
    pass


# Constants
INT_TYPE = type(0)
STR_TYPE = type("")
MAX_LINE_LEN = 100  # for line breaks

# text matching patterns
reGameTreeStart = re.compile(r'\s*\(')
reGameTreeEnd = re.compile(r'\s*\)')
reGameTreeNext = re.compile(r'\s*([;()])')
reNodeContents = re.compile(r'\s*([A-Za-z]+(?=\s*\[))')
rePropertyStart = re.compile(r'\s*\[')
rePropertyEnd = re.compile(r'\]')
reEscape = re.compile(r'\\')
reLineBreak = re.compile(r'\r\n?|\n\r?')  # CR, LF, CR/LF, LF/CR
reCharsToEscape = re.compile(r'[]\\]')  # characters that need to be \escaped


# for control characters (except LF \012 & CR \015): convert to spaces


def _escape_text(text):
    """ Adds backslash-escapes to property value characters that need them."""
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
    """ Converts control characters in 'text' to spaces. Override for variant
        behaviour."""
    return text.translate(str.maketrans("\000\001\002\003\004\005\006\007\010\011\013\014\016\017\020"
                                        "\021\022\023\024\025\026\027\030\031\032\033\034\035\036\037", " " * 30))


class Collection(List):
    """
    An SGF collection: multiple 'GameTree''s. Instance atributes:
    - self[.data] : list of 'GameTree' -- One 'GameTree' per game."""

    def __str__(self):
        """ SGF representation. Separates game trees with a blank line."""
        return "\n\n".join([str(x) for x in self.data])

    def cursor(self, game_num=0):
        """ Returns a 'Cursor' object for navigation of the given 'GameTree'."""
        return Cursor(self[game_num])

    def save_to_file(self, path_to_save):
        with open(path_to_save, mode='w', encoding='utf-8') as f:
            f.write(str(self))


class Property(List):
    """
    An SGF property: a set of label and value(s). Instance attributes:
    - self[.data] : list -- property values.
    - self.id : string -- SGF standard property label.
    - self.name : string -- actual label used in the SGF data. For example, the
      property 'CoPyright[...]' has name 'CoPyright' and id 'CP'."""

    def __init__(self, pid, values, name=None):
        """
            Initialize the 'Property'. Arguments:
            - id : string
            - name : string (optional) -- If not given, 'self.name'
            - nodelist : 'GameTree' or list of 'Node' -- Stored in 'self.data'.
            - variations : list of 'GameTree' -- Stored in 'self.variations'."""
        List.__init__(self, values)  # XXX will _convert work here?
        self.pid = pid
        self.name = name or pid

    def __str__(self):
        return self.name + "[" + "][".join([_escape_text(x) for x in self]) + "]"

    def copy(self):
        n_values = [v for v in self]
        return Property(self.pid, n_values, self.name)


class Node(Dictionary):
    """
    An SGF node. Instance Attributes:
    - self[.data] : ordered dictionary -- '{Property.id:Property}' mapping.
      (Ordered dictionary: allows offset-indexed retrieval). Properties *must*
      be added using 'self.add_property()'.

    Example: Let 'n' be a 'Node' parsed from ';B[aa]BL[250]C[comment]':
    - 'str(n["BL"])'  =>  '"BL[250]"'
    - 'str(n[0])'     =>  '"B[aa]"'
    - 'map(str, n)'   =>  '["B[aa]","BL[250]","C[comment]"]'"""

    def __init__(self, p_list=None):
        """
            Initializer. Argument:
            - p_list: Node or list of 'Property'."""
        if p_list is None:
            p_list = []
        Dictionary.__init__(self)
        self.order = []
        for p in p_list:
            self.add_property(p)

    def copy(self):
        p_list = []
        for prop in self.order:
            p_list.append(prop.copy())
        return Node(p_list)

    def __getitem__(self, key):
        """ On 'self[key]', 'x in self', 'for x in self'. Implements all
            indexing-related operations. Allows both key- and offset-indexed
            retrieval. Membership and iteration ('in', 'for') repeatedly index
            from 0 until 'IndexError'."""
        if type(key) is INT_TYPE:
            return self.order[key]
        elif type(key) is STR_TYPE:
            return self.data[key]
        else:
            return List(self)[key]

    def __setitem__(self, key, x):
        """ On 'self[key]=x'. Allows assignment to existing items only. Raises
            'DirectAccessError' on new item assignment."""
        if key in self.data:
            self.order[self.order.index(self[key])] = x
            Dictionary.__setitem__(self, key, x)
        else:
            raise DirectAccessError("Properties may not be added directly; use add_property() instead.")

    def __delitem__(self, key):
        """ On 'del self[key]'. Updates 'self.order' to maintain consistency."""
        self.order.remove(self[key])
        Dictionary.__delitem__(self, key)

    def __str__(self):
        """ SGF representation, with proper line breaks between properties."""
        if len(self):
            s = ";" + str(self[0])
            l = len(s.split("\n")[-1])  # accounts for line breaks within Properties
            for p in map(str, self[1:]):
                if l + len(p.split("\n")[0]) > MAX_LINE_LEN:
                    s = s + "\n"
                s = s + p
                l = len(s.split("\n")[-1])
            return s
        else:
            return ";"

    def update(self, n_dict):
        """ 'Dictionary' method not applicable to 'Node'. Raises
            'DirectAccessError'."""
        raise DirectAccessError("The update() method is not supported by Node; use add_property() instead.")

    def add_property(self, prop):
        """
            Adds a 'Property' to this 'Node'. Checks for duplicate properties
            (illegal), and maintains the property order. Argument:
            - prop : 'Property'"""
        if prop.pid in self.data:
            self.append_data(prop.pid, prop[:])
        # raise DuplicatePropertyError
        else:
            self.data[prop.pid] = prop
            self.order.append(prop)

    def append_data(self, pid, values):
        new_prop = Property(pid, self.data[pid][:] + values)
        self.data[pid] = new_prop
        for i in range(0, len(self.order)):
            if self.order[i].pid == pid:
                self.order[i] = new_prop


class Cursor:
    """
    'GameTree' navigation tool. Instance attributes:
    - self.game : 'GameTree' -- The root 'GameTree'.
    - self.game_tree : 'GameTree' -- The current 'GameTree'.
    - self.node : 'Node' -- The current Node.
    - self.node_num : integer -- The offset of 'self.node' from the root of
      'self.game'. The node_num of the root node is 0.
    - self.index : integer -- The offset of 'self.node' within 'self.game_tree'.
    - self.stack : list of 'GameTree' -- A record of 'GameTree''s traversed.
    - self.children : list of 'Node' -- All child nodes of the current node.
    - self.atEnd : boolean -- Flags if we are at the end of a branch.
    - self.atStart : boolean -- Flags if we are at the start of the game."""

    def __init__(self, game_tree):
        """ Initialize root 'GameTree' and instance variables."""
        self.game_tree = self.game = game_tree  # root GameTree
        self.node_num = 0
        self.index = 0
        self.stack = []
        self.node = self.game_tree[self.index]
        self._set_children()
        self._set_flags()

    def reset(self):
        """ Set 'Cursor' to point to the start of the root 'GameTree', 'self.game'."""
        self.game_tree = self.game
        self.node_num = 0
        self.index = 0
        self.stack = []
        self.node = self.game_tree[self.index]
        self._set_children()
        self._set_flags()

    def next(self, varnum=0):
        """
            Moves the 'Cursor' to & returns the next 'Node'. Raises
            'GameTreeEndError' if the end of a branch is exceeded. Raises
            'GameTreeNavigationError' if a non-existent variation is accessed.
            Argument:
            - varnum : integer, default 0 -- Variation number. Non-zero only
              valid at a branching, where variations exist."""
        if self.index + 1 < len(self.game_tree):  # more main line?
            if varnum != 0:
                raise GameTreeNavigationError("Nonexistent variation.")
            self.index = self.index + 1
        elif self.game_tree.variations:  # variations exist?
            if varnum < len(self.game_tree.variations):
                self.stack.append(self.game_tree)
                self.game_tree = self.game_tree.variations[varnum]
                self.index = 0
            else:
                raise GameTreeNavigationError("Nonexistent variation.")
        else:
            raise GameTreeEndError
        self.node = self.game_tree[self.index]
        self.node_num = self.node_num + 1
        self._set_children()
        self._set_flags()
        return self.node

    def previous(self):
        """ Moves the 'Cursor' to & returns the previous 'Node'. Raises
            'GameTreeEndError' if the start of a branch is exceeded."""
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

    def push_node(self, node):
        var = GameTree([node])
        self.game_tree.pushTree(var, self.index)
        self._set_children()
        self._set_flags()

    def append_node(self, node):
        if self.index + 1 < len(self.game_tree) or self.game_tree.variations:
            var = GameTree([node])
            self.game_tree.append_tree(var, self.index)
            self._set_children()
            self._set_flags()
        else:
            self.game_tree.append_node(node)
            self._set_children()
            self._set_flags()

    def _set_children(self):
        """ Sets up 'self.children'."""
        if self.index + 1 < len(self.game_tree):
            self.children = [self.game_tree[self.index + 1]]
        else:
            self.children = [x[0] for x in self.game_tree.variations]

    def _set_flags(self):
        """ Sets up the flags 'self.atEnd' and 'self.atStart'."""
        self.atEnd = not self.game_tree.variations and (self.index + 1 == len(self.game_tree))
        self.atStart = not self.stack and (self.index == 0)


class GameTree(List):
    """
    An SGF game tree: a game or variation. Instance attributes:
    - self[.data] : list of 'Node' -- game tree 'trunk'.
    - self.variations : list of 'GameTree' -- 0 or 2+ variations.
      'self.variations[0]' contains the main branch (sequence actually played)."""

    def __init__(self, nodelist=None, variations=None):
        """
            Initialize the 'GameTree'. Arguments:
            - nodelist : 'GameTree' or list of 'Node' -- Stored in 'self.data'.
            - variations : list of 'GameTree' -- Stored in 'self.variations'."""
        List.__init__(self, nodelist)
        self.variations = variations or []

    def __str__(self):
        """ SGF representation, with proper line breaks between nodes."""
        if len(self):
            s = "(" + str(self[0])  # append the first Node automatically
            l = len(s.split("\n")[-1])  # accounts for line breaks within Nodes
            for n in [str(x) for x in self[1:]]:
                if l + len(n.split("\n")[0]) > MAX_LINE_LEN:
                    s = s + "\n"
                s = s + n
                l = len(s.split("\n")[-1])
            return s + "\n".join([str(x) for x in [""] + self.variations]) + ")"
        else:
            return ""  # empty GameTree illegal; "()" illegal

    def mainline(self):
        """ Returns the main line of the game (variation A) as a 'GameTree'."""
        if self.variations:
            return GameTree(self.data + self.variations[0].mainline())
        else:
            return self

    def cursor(self):
        """ Returns a 'Cursor' object for navigation of this 'GameTree'."""
        return Cursor(self)

    def append_tree(self, n_tree, index):
        if index + 1 < len(self.data):
            subtree = GameTree(self.data[index + 1:], self.variations)
            self.data = self.data[:index + 1]
            self.variations = [subtree, n_tree]
        else:
            self.variations.append(n_tree)

    def push_tree(self, ntree, index):
        if index + 1 < len(self.data):
            subtree = GameTree(self.data[index + 1:], self.variations)
            self.data = self.data[:index + 1]
            self.variations = [ntree, subtree]
        else:
            self.variations = [ntree] + self.variations

    def append_node(self, node):
        self.data.append(node)

    def property_search(self, pid, get_all=0):
        """
            Searches this 'GameTree' for nodes containing matching properties.
            Returns a 'GameTree' containing the matched node(s). Arguments:
            - pid : string -- ID of properties to search for.
            - getall : boolean -- Set to true (1) to return all 'Node''s that
              match, or to false (0) to return only the first match."""
        matches = []
        for n in self:
            if pid in n.data:
                matches.append(n)
                if not get_all:
                    break
        else:  # get_all or not matches:
            for v in self.variations:
                matches = matches + v.property_search(pid, get_all)
                if not get_all and matches:
                    break
        return GameTree(matches)


class SGFParser:
    """
    Parser for SGF data. Creates a tree structure based on the SGF standard
    itself. 'SGFParser.parse()' will return a 'Collection' object for the entire
    data.

    Instance Attributes:
    - self.data : string -- The complete SGF data instance.
    - self.data_len : integer -- Length of 'self.data'.
    - self.index : integer -- Current parsing position in 'self.data'."""

    def __init__(self, data):
        """ Initialize the instance attributes. See the class itself for info."""
        self.data = data
        self.data_len = len(data)
        self.index = 0

    def parse(self):
        """ Parses the SGF data stored in 'self.data', and returns a 'Collection'."""
        c = Collection()
        while self.index < self.data_len:
            g = self.parse_one_game()
            if g:
                c.append(g)
            else:
                break
        return c

    def parse_one_game(self):
        """ Parses one game from 'self.data'. Returns a 'GameTree' containing
            one game, or 'None' if the end of 'self.data' has been reached."""
        if self.index < self.data_len:
            match = reGameTreeStart.match(self.data, self.index)
            if match:
                self.index = match.end()
                return self.parse_game_tree()
        return None

    def parse_game_tree(self):
        """ Called when "(" encountered, ends when a matching ")" encountered.
            Parses and returns one 'GameTree' from 'self.data'. Raises
            'GameTreeParseError' if a problem is encountered."""
        g = GameTree()
        while self.index < self.data_len:
            match = reGameTreeNext.match(self.data, self.index)
            if match:
                self.index = match.end()
                if match.group(1) == ";":  # found start of node
                    if g.variations:
                        raise GameTreeParseError("A node was encountered after a variation.")
                    g.append(self.parse_node())
                elif match.group(1) == "(":  # found start of variation
                    g.variations = self.parse_variations()
                else:  # found end of GameTree ")"
                    return g
            else:  # error
                raise GameTreeParseError
        return g

    def parse_variations(self):
        """ Called when "(" encountered inside a 'GameTree', ends when a
            non-matching ")" encountered. Returns a list of variation
            'GameTree''s. Raises 'EndOfDataParseError' if the end of 'self.data'
            is reached before the end of the enclosing 'GameTree'."""
        v = []
        while self.index < self.data_len:
            # check for ")" at end of GameTree, but don't consume it
            match = reGameTreeEnd.match(self.data, self.index)
            if match:
                return v
            g = self.parse_game_tree()
            if g:
                v.append(g)
            # check for next variation, and consume "("
            match = reGameTreeStart.match(self.data, self.index)
            if match:
                self.index = match.end()
        raise EndOfDataParseError

    def parse_node(self):
        """ Called when ";" encountered (& is consumed). Parses and returns one
            'Node', which can be empty. Raises 'NodePropertyParseError' if no
            property values are extracted. Raises 'EndOfDataParseError' if the
            end of 'self.data' is reached before the end of the node (i.e., the
            start of the next node, the start of a variation, or the end of the
            enclosing game tree)."""
        n = Node()

        while self.index < self.data_len:
            match = reNodeContents.match(self.data, self.index)
            if match:
                self.index = match.end()
                pv_list = self.parse_property_value()
                if pv_list:
                    n.add_property(Property(match.group(1), pv_list))
                else:
                    raise NodePropertyParseError
            else:  # reached end of Node
                return n

        raise EndOfDataParseError

    def parse_property_value(self):
        """ Called when "[" encountered (but not consumed), ends when the next
            property, node, or variation encountered. Parses and returns a list
            of property values. Raises 'PropertyValueParseError' if there is a
            problem."""
        pv_list = []
        while self.index < self.data_len:
            match = rePropertyStart.match(self.data, self.index)
            if match:
                self.index = match.end()
                v = ""  # value
                # scan for escaped characters (using '\'), unescape them (remove linebreaks)
                mend = rePropertyEnd.search(self.data, self.index)
                mesc = reEscape.search(self.data, self.index)
                while mesc and mend and (mesc.end() < mend.end()):
                    # copy up to '\', but remove '\'
                    v = v + self.data[self.index:mesc.start()]
                    mbreak = reLineBreak.match(self.data, mesc.end())
                    if mbreak:
                        self.index = mbreak.end()  # remove linebreak
                    else:
                        v = v + self.data[mesc.end()]  # copy escaped character
                        self.index = mesc.end() + 1  # move to point after escaped char
                    mend = rePropertyEnd.search(self.data, self.index)
                    mesc = reEscape.search(self.data, self.index)
                if mend:
                    v = v + self.data[self.index:mend.start()]
                    self.index = mend.end()
                    pv_list.append(_convert_control_chars(v))
                else:
                    raise PropertyValueParseError
            else:  # reached end of Property
                break

        if len(pv_list) >= 1:
            return pv_list
        else:
            raise PropertyValueParseError


class RootNodeSGFParser(SGFParser):
    """ For parsing only the first 'GameTree''s root Node of an SGF file."""

    def parse_node(self):
        """ Calls 'SGFParser.parseNode()', sets 'self.index' to point to the end
            of the data (effectively ending the 'GameTree' and 'Collection'),
            and returns the single (root) 'Node' parsed."""
        n = SGFParser.parse_node(self)  # process one Node as usual
        self.index = self.data_len  # set end of data
        return n  # we're only interested in the root node


# TESTS

def self_test_1():
    c = Collection()
    c.append("GM [1]US[someone]CoPyright[Permission to reproduce this game is given.]GN[a-b]EV[None]RE[B+Resign]")
    c.append("AB[ba][bb]")
    print(c)
    pass


def self_test_2():
    p = Property('GM', ["as"])
    print(p)
    pass


def self_test_3():
    p = Node([Property('GM', ["as"]), Property('SZ', ["as", "ac", "ab"])])
    print(p)
    pass


def self_test_4():
    sgf_data = r"""(;GM [1]US[someone]CoPyright[\
  Permission to reproduce this game is given.]GN[a-b]EV[None]RE[B+Resign]
PW[a]WR[2k*]PB[b]BR[4k*]PC[somewhere]DT[2000-01-16]SZ[19]TM[300]KM[4.5]
HA[3]AB[pd][dp][dd];W[pp];B[nq];W[oq]C[ x started observation.
](;B[qc]C[ [b\]: \\ hi x! ;-) \\];W[kc])(;B[hc];W[oe]))"""
    c = SGFParser(sgf_data)
    print(c.parse())
    pass


def self_test_5():
    """ Canned data test case"""
    sgfdata = r"""       (;GM [1]US[someone]CoPyright[\
  Permission to reproduce this game is given.]GN[a-b]EV[None]RE[B+Resign]
PW[a]WR[2k*]PB[b]BR[4k*]PC[somewhere]DT[2000-01-16]SZ[19]TM[300]KM[4.5]
HA[3]AB[pd][dp][dd];W[pp];B[nq];W[oq]C[ x started observation.
](;B[qc]C[ [b\]: \\ hi x! ;-) \\];W[kc])(;B[hc];W[oe]))   """
    print("\n\n********** Self-Test 1 **********\n")
    print("Input data:\n")
    print(sgfdata)
    print("\n\nParsed data: ")
    col = SGFParser(sgfdata).parse()
    print("done\n")
    cstr = str(col)
    print(cstr, "\n")
    print("Mainline:\n")
    m = col[0].mainline()
    print(m, "\n")
    print("as GameTree:\n")
    print(GameTree(m), "\n")
    print("Tree traversal (forward):\n")
    c = col.cursor()
    while 1:
        print("nodenum: %s; index: %s; children: %s; node: %s" % (c.node_num, c.index, len(c.children), c.node))
        if c.atEnd:
            break
        c.next()
    print("\nTree traversal (backward):\n")
    while 1:
        print("nodenum: %s; index: %s; children: %s; node: %s" % (c.node_num, c.index, len(c.children), c.node))
        if c.atStart:
            break
        c.previous()
    print("\nSearch for property 'B':")
    print(col[0].property_search("B", 1))
    print("\nSearch for property 'C':")
    print(col[0].property_search("C", 1))
    pass


if __name__ == '__main__':
    print(__doc__)  # show module's documentation string
    self_test_1()
    self_test_2()
    self_test_3()
    self_test_4()
    self_test_5()
