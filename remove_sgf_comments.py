from sgflib import SGFParser, Node, GameTree
import sys
import os

if __name__ == '__main__':
    game_list = []

    path = sys.argv[1]

    os.makedirs('cleaned_sgfs', exist_ok=True)

    if os.path.isdir(path):
        os.makedirs(os.path.join('cleaned_sgfs', path), exist_ok=True)
        for s in os.listdir(path):
            if os.path.splitext(s)[1] == '.sgf':
                game_list.append(os.path.join(path, s))
    else:
        game_list.append(path)

    count = 0
    for game in game_list:
        with open(game, 'r') as f:
            sgf = SGFParser(f.read()).parse().cursor().game_tree.mainline().cursor()
            new_sgf = GameTree()
            while not sgf.atEnd:
                new_node = Node()
                for prop in sgf.node:
                    if sgf.node[prop].label != 'C':
                        new_node.add_property(sgf.node[prop])

                new_sgf.append_node(new_node)
                sgf.next()
        with open(os.path.join('cleaned_sgfs', game), 'w') as f:
            f.write(str(new_sgf))
        
        count += 1
        
        if count % 1000:
            print(f"Files processed: {count/len(game_list)*100}%")
