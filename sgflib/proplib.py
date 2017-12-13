"""
SGF FF4 Specification

Move, Point & Stone type

In Go the Stone becomes Point and the Move and Point type are the same: two
lowercase letters.

The first letter designates the column (left to right), the second the row (top to bottom). The upper left part of the
board is used for smaller boards, e.g. letters "a"-"m" for 13*13.
A pass move is shown as '[]' or alternatively as '[tt]' (only for boards <= 19x19), i.e. applications should be able to
deal with both representations. '[tt]' is kept for compatibility with FF[3].
Using lowercase letters only the maximum board size is 26x26.

In FF[4] it is possible to specify board sizes upto 52x52. In this case uppercase letters are used to represent points
from 27-52, i.e. 'a'=1 ... 'z'=26 , 'A'=27 ... 'Z'=52


How to execute a move

When a B (resp. W) property is encountered, a stone of that color is placed on the given position (no matter what was
there before).
Then the application should check any W (resp. B) groups that are adjacent to the stone just placed. If they have no
liberties they should be removed and the prisoner count increased accordingly.
Lastly, the B (resp. W) group that the newest stone belongs to should be checked for liberties, and if it has no
liberties, it should be removed (suicide) and the prisoner count increased accordingly.

Properties

TW and TB points must be unique, i.e. it's illegal to list the same point in TB and TW within the same node.
"""


# EXCEPTIONS
class UnexpectedPropertyException(Exception):
    pass


class BaseProperty(object):
    def define_property(self, label):
        raise NotImplementedError()


# MOVE PROPERTIES
class BlackMove:
    label = 'B'
    info = ("Execute a black move. This is one of the most used properties in actual collections. As long as the given "
            "move is syntactically correct it should be executed.\nIt doesn't matter if the move itself is illegal "
            "(e.g. recapturing a ko in a Go game).\nHave a look at how to execute a Go-move. B and W properties must "
            "not be mixed within a node.")


class ExecuteIllegal:
    label = 'KO'
    info = ("Execute a given move (B or W) even it's illegal. This is an optional property, SGF viewers themselves "
            "should execute ALL moves. It's purpose is to make it easier for otherb applications (e.g. "
            "computer-players) to deal with illegal moves. A KO property without a black or white move within the same "
            "node is illegal.")


class MoveNumber:
    label = 'MN'
    info = ("Sets the move number to the given value, i.e. a move specified in this node has exactly this move-number. "
            "This can be useful for variations or printing.")


class WhiteMove:
    label = 'B'
    info = ("Execute a black move. This is one of the most used properties in actual collections. As long as the given "
            "move is syntactically correct it should be executed.\nIt doesn't matter if the move itself is illegal "
            "(e.g. recapturing a ko in a Go game).\nHave a look at how to execute a Go-move. B and W properties must "
            "not be mixed within a node.")


class MoveProperty(BaseProperty):
    def define_property(self, label):
        if label == 'B':
            return BlackMove()
        elif label == 'K0':
            return ExecuteIllegal()
        elif label == 'MN':
            return MoveNumber()
        elif label == 'W':
            return WhiteMove()
        else:
            raise UnexpectedPropertyException()


"""
Setup properties

Restrictions

AB, AW and AE must have unique points, i.e. it is illegal to place different colors on the same point within one node.
AB, AW and AE values which don't change the board, e.g. placing a black stone with AB[] over a black stone that's 
already there, is bad style. Applications may want to delete these values and issue a warning.
"""


class SetupProperty:
    pass


class BlackStones:
    label = 'AB'
    info = ("Add black stones to the board. This can be used to set up positions or problems. Adding is done by "
            "'overwriting' the given point with black stones. It doesn't matter what was there before. Adding a stone "
            "doesn't make any prisoners nor any other captures (e.g. suicide). Thus it's possible to create illegal "
            "board positions.\nPoints used in stone type must be unique.")


class EmptyPoints:
    label = 'AE'
    info = ("Clear the given points on the board. This can be used to set up positions or problems. Clearing is done "
            "by 'overwriting' the given points, so that they contain no stones. It doesn't matter what was there "
            "before.\nClearing doesn't count as taking prisoners.\nPoints must be unique.")


class WhiteStones:
    label = 'AW'
    info = ("Add white stones to the board. This can be used to set up positions or problems. Adding is done by "
            "'overwriting' the given point with black stones. It doesn't matter what was there before. Adding a stone "
            "doesn't make any prisoners nor any other captures (e.g. suicide). Thus it's possible to create illegal "
            "board positions.\nPoints used in stone type must be unique.")


# Game specific properties (GO)
handicap = {
    'label': 'HA',
    'value': 'number',
    'type': 'game-info',
    'info': "Defines the number of handicap stones (>=2).\n"
            "If there is a handicap, the position should be set up with AB within the same node.\n"
            "HA itself doesn't add any stones to the board, nor does it imply any particular way of placing "
            "the handicap stones."
}
komi = {
    'label': 'KM',
    'value': 'real',
    'type': 'game-info',
    'info': 'Defines the komi.'
}
black_territory = {
    'label': 'TB',
    'value': 'elist',
    'type': None,
    'info': 'Specifies the black territory or area (depends on rule set used).\n'
            'Points must be unique.'
}
white_territory = {
    'label': 'TW',
    'value': 'elist',
    'type': None,
    'info': 'Specifies the white territory or area (depends on rule set used).\n'
            'Points must be unique.'
}
