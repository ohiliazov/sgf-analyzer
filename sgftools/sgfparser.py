import re

sgf_fn = 'D:/Python/leela-analysis-36/test_sgf/test.sgf'

with open(sgf_fn, 'r') as sgf_file:
    sgf = sgf_file.read()

# Nice pattern that captures properties like:
# LB[on:A][pb:?]
# C[test[] or C[test\]]
reProperty = re.compile(r'(?P<label>[A-Z]{1,2})(?P<values>(\[[^\]\\]*(?:\\.[^\]\\]*)*\])+)')


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

index = 0
data_len = len(sgf)
node_list_index = 0
nodes = [[] for i in range(sgf.count(';'))]
while index < data_len:
    if sgf[index] == ';':
        node_list_index += 1
    match = reProperty.match(sgf, index)
    if match:
        index = match.end()
        nodes[node_list_index].append([match.group('label'), match.group('values')])
    else:
        index += 1
print([str(n) for n in nodes])
print(Property('C', ['bfd', 'dsf', 'sdfvokp']))
print(Node([Property('C', ['bfd', 'dsf', 'sdfvokp']),Property('B', ['bfd', 'dsf', 'sdfvokp']),Property('W', ['bfd', 'dsf', 'sdfvokp'])]))