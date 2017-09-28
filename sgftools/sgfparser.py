import re

property_dict = {
    'GM': 'GM[1]',  # Game name
    'FF': 'FF[4]',  # File format
    'CA': 'CA[UTF-8]',  # Encoding
    'AP': 'AP[CGoban:3]',  # Application
    'ST': 'ST[2]',
    'RU': 'RU[Japanese]',  # Rule set
    'SZ': 'SZ[19]',  # Board size
    'HA': 'HA[3]',  # Handicap >= 2
    'KM': 'KM[0.50]',  # Komi
    'TM': 'TM[10]',  # Main time
    'OT': 'OT[1/7 Canadian]',  # Overtime
    'PW': 'PW[RoyalCrown]',  # White player
    'PB': 'PB[Gelya]',  # Black player
    'WR': 'WR[6d]',  # White rank
    'BR': 'BR[3d]',  # Black rank
    'DT': 'DT[2017-09-18]',  # Date played
    'PC': 'PC[The KGS Go Server at http://www.gokgs.com/]',  # Place
    'AB': 'AB[pd][dp][pp]',  # Add black stones
    'AW': 'AW[dk][kd][kk]',  # Add white stones
    'C': 'C[Gelya [3d\]: hi\n]',  # Comment
    'RE': 'RE[B+3.50]',  # Game result
    'B': 'B[cf]',  # Black move
    'W': 'W[dd]',  # White move
    'BL': 'BL[5.07]',
    'WL': 'WL[4.697]',
    'OB': 'OB[3]',
    'OW': 'OW[1]',
    'TW': 'TW[aa][ba][ca][fa]'
}

reGameTreeStart = re.compile(r'\s*\(')
reGameTreeEnd = re.compile(r'\s*\)')
reGameTreeNext = re.compile(r'\s*([;()])')
reNodeContents = re.compile(r'\s*([A-Za-z]+(?=\s*\[))')
rePropertyStart = re.compile(r'\s*\[')
rePropertyEnd = re.compile(r'\]')
reEscape = re.compile(r'\\')
reLineBreak = re.compile(r'\r\n?|\n\r?')  # CR, LF, CR/LF, LF/CR


class Property:
    def __init__(self, label: str, values: list):
        self.label = label
        self.values = values

    def __str__(self):
        return self.label + '[' + "][".join([str(x) for x in self.values]) + ']'

    def add_value(self, v_list: list):
        for value in v_list:
            self.values.append(value)


def parse_property(data: str):
    reProperty = r"(?P<label>[A-Z]{1,2})(?P<values>\[[\w\W]+\])+"

    match = re.match(reProperty, data)

    def parse_property_value(v_list):
        pv_list = []

        index = 0
        max_index = len(v_list)

        while index < max_index:
            match_start = rePropertyStart.match(v_list, index)
            prop_value = ""
            if match_start:
                index = match_start.end()

                match_end = rePropertyEnd.search(v_list, index)
                match_esc = reEscape.search(v_list, index)
                while match_esc and match_end and (match_esc.end() < match_end.end()):
                    prop_value += v_list[index:match_esc.start()]
                    match_break = reLineBreak.match(v_list, match_esc.end())

                    if match_break:
                        index = match_break.end()  # remove linebreak
                    else:
                        prop_value += v_list[match_esc.end()]  # copy escaped character
                        index = match_esc.end() + 1  # move to point after escaped char
                    match_end = rePropertyEnd.search(v_list, index)
                    match_esc = reEscape.search(v_list, index)

                if match_end:
                    prop_value += v_list[index:match_end.start()]
                    index = match_end.end()
                    pv_list.append(prop_value)
                else:
                    raise Exception
            else:
                break

        if len(pv_list) >= 1:
            return pv_list
        else:
            raise Exception

    label = match.group('label')
    values = parse_property_value(match.group('values'))

    return Property(label, values)


node_dict = {
    'A': ("GM[1]FF[4]CA[UTF-8]AP[CGoban:3]ST[2]RU[Japanese]SZ[19]HA[3]KM[0.50]TM[10]OT[1/7 Canadian]\n"
          "PW[RoyalCrown]PB[Gelya]WR[6d]BR[3d]DT[2017-09-18]PC[The KGS Go Server at http://www.gokgs.com/]"
          "AB[pd][dp][pp]C[Gelya [3d\]: hi\n]RE[B+3.50];")
}


class Node:
    def __init__(self, prop_list=None):
        self.prop_list = prop_list if prop_list is not None else []
        self.order = []

    def __str__(self):
        return ';' + "".join([str(x) for x in self.prop_list])

    def add_property(self, prop: Property):
        self.prop_list.append(prop)


def parse_node(data):
    index = 0
    data_len = len(data)
    node = Node()
    rePropertyEnd = re.compile(r"\]")
    while index < data_len:
        match = reNodeContents.match(data, index)
        if match:
            print(data[index:match.end()])
            index = match.end()
        else:
            break

node = Node([Property('C', ['Hi']), Property('B', ['cc'])])
for node in node_dict:
    print(parse_node(node_dict[node]))
