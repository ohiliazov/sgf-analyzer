import re, sys


# PARSING EXCEPTIONS
class PropertyValueParseError(Exception):
    """ Raised by 'parse_property_value()'."""
    pass


class PropertyParseError(Exception):
    """ Raised by 'parse_property()'."""
    pass


class NodeParseError(Exception):
    """ Raised by 'parse_node()'."""
    pass


class GameTreeParseError(Exception):
    """ Raised by 'parse_game_tree()'."""
    pass


sgf_fn = 'D:/Python/leela-analysis-36/test_sgf/test.sgf'

with open(sgf_fn, 'r') as sgf_file:
    sgf = sgf_file.read()

rePropertyValue = re.compile(r'\['  # Open square brackets
                             r'(?P<value>[^\]\\]*(?:\\.[^\]\\]*)*)'  # Any characters except non-escaped ']'
                             r'\]', re.DOTALL)  # Close square brackets

reProperty = re.compile(r'(?P<label>[A-Z]{1,2})'  # Label of property
                        r'(?P<values>(\[[^\]\\]*(?:\\.[^\]\\]*)*\])+)', re.DOTALL)  # Repeated rePropertyValue

reNode = re.compile(r'\s*(?P<node>;'  # Start of node
                    r'([A-Z]{1,2}(\[[^\]\\]*(?:\\.[^\]\\]*)*\])+)+)\s*', re.DOTALL)  # Repeated reProperty

reGameTreeStart = re.compile(r'(\()'  # Open brackets
                             r'(?:(?:\()*|(?:;(?:[A-Z]{1,2}(?:\[[^\]\\]*(?:\\.[^\]\\]*)*\])+)+)*)',
                             re.DOTALL)  # reNode or brackets

reGameTreeEnd = re.compile(r'(?:(?:;(?:[A-Z]{1,2}(?:\[[^\]\\]*(?:\\.[^\]\\]*)*\])+)+)*|(?:\))*)'  # reNode or brackets
                           r'(\))', re.DOTALL)  # Close brackets


class Property:
    def __init__(self, label, v_list=None):
        self.label = label
        self.values = v_list or []

    def __str__(self):
        return self.label + "[" + "][".join([v for v in self.values]) + "]"


class Node:
    def __init__(self, p_list=None):
        self.p_list = p_list or []

    def __str__(self):
        return ';' + ''.join([str(x) for x in self.p_list])


class GameTree:
    def __init__(self, n_list=None, v_list=None):
        self.n_list = n_list or []
        self.v_list = v_list or []

    def __str__(self):
        if len(self.n_list) > 0:
            return "".join([str(x) for x in self.n_list])
        elif len(self.v_list) > 0:
            return "(" + ")\n(".join([str(x) for x in self.v_list]) + ")"


def parse_property_value(values: str):
    """
    Split property values into list of values
    :param values: string - [value_1][value_2]..[value_n]
    :return: list - ['value_1', 'value_2', .., 'value_n']
    """
    value_list = []
    index = 0
    data_len = len(values)
    while index < data_len:
        m_value = rePropertyValue.match(values, index)
        if m_value:
            value_list.append(m_value.group('value'))
            index = m_value.end()
        else:
            break

    if len(value_list) > 0:
        return value_list
    else:
        raise PropertyValueParseError("Failed to parse: %s" % values)


def parse_property(prop: str):
    """
    Parse property string to Property class
    :param prop: string - PR[value_1][value_2]..[value_n]
    :return: Property('PR', ['value_1','value_2', .., 'value_n'])
    """
    m_prop = reProperty.match(prop)
    if m_prop:
        label = m_prop.group('label')
        values = parse_property_value(m_prop.group('values'))
        return Property(label, values)
    else:
        raise PropertyParseError("Failed to parse: %s" % prop)


def parse_node(node: str):
    """
    Parse node string to list of properties.
    :param node: string - ;PR[values]PR[values]..PR[values]
    :return: Node(Property, Property, .., Property)
    """
    p_list = []
    index = 1  # Skip semicolon
    data_len = len(node)
    while index < data_len:
        m_prop = reProperty.match(node, index)
        if m_prop:
            p_list.append(parse_property(m_prop.group(0)))
            index = m_prop.end()
        else:
            raise NodeParseError("Failed to parse: %s" % node)
    return Node(p_list)


def parse_game_tree(game_tree: str, node=False):
    n_list = []
    index = 0
    data_len = len(game_tree)
    while index < data_len:
        m_node = reNode.match(game_tree, index)
        if m_node:
            n_list.append(parse_node(m_node.group('node')))
            index = m_node.end()
        elif game_tree[index] == '(':
            n_list.append(parse_variations(game_tree[index:]))
            break
        else:
            raise GameTreeParseError("Failed to parse: %s" % game_tree)
    return GameTree(n_list)


def parse_variations(variations: str):
    v_list = []
    s_list = [(start.start(), '(') for start in reGameTreeStart.finditer(variations)]
    e_list = [(end.end(), ')') for end in reGameTreeEnd.finditer(variations)]

    def find_matching_brackets(brackets):
        matches = []
        counter = 0
        index = brackets[0][0]

        for i, v in brackets:
            counter += 1 if v == '(' else -1

            if counter == 0:
                matches.append(slice(index+1, i-1))
                index = min([k for k, v in brackets if k > i], default=0)

        return matches

    matches = find_matching_brackets(sorted(s_list + e_list))
    for match in matches:
        v_list.append(parse_game_tree(variations[match], True))
    return GameTree(v_list=v_list)


# print(parse_property_value('[on:A][qo:B]'))
# print(parse_property_value('[sd]'))
# print(parse_property('LB[on:A][qo:B]'))
# print(parse_node(';LB[on:A][qo:B]C[hello]'))
GT = parse_game_tree(""";GM[1]FF[4]CA[UTF-8]AP[CGoban:3]ST[2]RU[Japanese]SZ[19]KM[6.50]PW[White]PB[Black];B[pd]C[test[];W[dp]C[test\]]
;B[pq]C[test(];W[dd]C[test)];B[fq]C[test;];W[cn];B[jp];W[qn]
    (;B[qp]
        (;W[pj];B[qh];W[on];B[pm];W[pn];B[mp])
        (;W[qk];B[qi])
    )
    (;B[po];W[rp];B[ql]TR[qn][rp]SQ[po][pq];W[pn]LB[on:A][qo:B]
        (;B[qo];W[ro];B[rm];W[rn];B[qq])
        (;B[on];W[om];B[nn];W[nm];B[mn])
    )
""")
print(GT.n_list[9].v_list[0].n_list[0])
