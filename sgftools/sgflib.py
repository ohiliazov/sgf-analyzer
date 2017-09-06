import re

from sgftools.typelib import List, Dictionary


# Parsing Exceptions

class EndOfDataParseError(Exception):
    """ Raised by 'SGFParser.parseVariations()', 'SGFParser.parseNode()'."""
    pass


class GameTreeParseError(Exception):
    """ Raised by 'SGFParser.parse_game_tree()'."""
    pass


class NodePropertyParseError(Exception):
    """ Raised by 'SGFParser.parseNode()'."""
    pass


class PropertyValueParseError(Exception):
    """ Raised by 'SGFParser.parsePropertyValue()'."""
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
MAX_LINE_LEN = 76  # for line breaks

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
control_chars = "\000\001\002\003\004\005\006\007\010\011\013\014\016\017\020" \
                "\021\022\023\024\025\026\027\030\031\032\033\034\035\036\037"


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


class Collection(List):
    """
    An SGF collection: multiple 'GameTree''s. Instance atributes:
    - self[.data] : list of 'GameTree' -- One 'GameTree' per game."""

    def __str__(self):
        """ SGF representation. Separates game trees with a blank line."""
        return "\n\n".join(map(str, self.data))

        # def cursor(self, game_num=0):
        #     """ Returns a 'Cursor' object for navigation of the given 'GameTree'."""
        #     return Cursor(self[game_num])


class Property(List):
    """
    An SGF property: a set of label and value(s). Instance attributes:
    - self[.data] : list -- property values.
    - self.id : string -- SGF standard property label.
    - self.name : string -- actual label used in the SGF data. For example, the
      property 'CoPyright[...]' has name 'CoPyright' and id 'CP'."""

    def __init__(self, id, values, name=None):
        """
            Initialize the 'Property'. Arguments:
            - id : string
            - name : string (optional) -- If not given, 'self.name'
            - nodelist : 'GameTree' or list of 'Node' -- Stored in 'self.data'.
            - variations : list of 'GameTree' -- Stored in 'self.variations'."""
        List.__init__(self, values)  # XXX will _convert work here?
        self.id = id
        self.name = name or id

    def __str__(self):
        return self.name + "[" + "][".join([_escape_text(x) for x in self]) + "]"

    def copy(self):
        n_values = [v for v in self]
        return Property(self.id, n_values, self.name)


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

    def __init__(self, plist=None):
        """
            Initializer. Argument:
            - plist: Node or list of 'Property'."""
        if plist is None:
            plist = []
        Dictionary.__init__(self)
        self.order = []
        for p in plist:
            self.add_property(p)

    def copy(self):
        plist = []
        for prop in self.order:
            plist.append(prop.copy())
        return Node(plist)

    def __getitem__(self, key):
        """ On 'self[key]', 'x in self', 'for x in self'. Implements all
            indexing-related operations. Allows both key- and offset-indexed
            retrieval. Membership and iteration ('in', 'for') repeatedly index
            from 0 until 'IndexError'."""
        if type(key) is INT_TYPE:
            return self.order[key]
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
        if prop.id in self.data:
            self.append_data(prop.id, prop[:])
        # raise DuplicatePropertyError
        else:
            self.data[prop.id] = prop
            self.order.append(prop)

    def make_property(self, id, value_list):
        """
            Create a new 'Property'. Override/extend to create 'Property'
            subclass instances (move, setup, game-info, etc.). Arguments:
            - id : string
            - value_list : 'Property' or list of values"""
        return Property(id, value_list)

    def append_data(self, id, values):
        new_prop = Property(id, self.data[id][:] + values)
        self.data[id] = new_prop
        for i in range(0, len(self.order)):
            if self.order[i].id == id:
                self.order[i] = new_prop


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
                    l = 0
                s = s + n
                l = len(s.split("\n")[-1])
            return s + "\n".join([str(["" + x]) for x in self.variations]) + ")"
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
            if pid in n:
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
                        raise GameTreeParseError(
                            "A node was encountered after a variation.")
                    g.append(Node(self.parseNode()))
                elif match.group(1) == "(":  # found start of variation
                    g.variations = self.parseVariations()
                else:  # found end of GameTree ")"
                    return g
            else:  # error
                raise GameTreeParseError
        return g

    pass


def self_test_1():
    c = Collection()
    c.append("AW[aa][ab]")
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


if __name__ == '__main__':
    # print(__doc__)  # show module's documentation string
    self_test_1()
    self_test_2()
    self_test_3()
    self_test_4()