import re
import os
import sys


def remove_comments(text):
    return re.sub("C\[[\w\W]*(?<!\\\\)]", '', text)


if __name__ == '__main__':
    games = []
    if os.path.isdir(sys.argv[1]):
        for p in os.listdir(sys.argv[1]):
            games.appens(os.join(sys.argv[1], p))
    else:
        games = [sys.argv[1],]
    
    for game in games:
        with open(game, 'r') as f:
            sgf = f.read()
        with open(game, 'w') as f:
            f.write(remove_comments(sgf))
