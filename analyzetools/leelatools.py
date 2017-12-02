def add_moves_to_leela(cursor, leela):
    this_move = None

    if 'W' in cursor.node.keys():
        this_move = cursor.node['W'].data[0]
        leela.add_move('white', this_move)

    if 'B' in cursor.node.keys():
        this_move = cursor.node['B'].data[0]
        leela.add_move('black', this_move)

    # SGF commands to add black or white stones, often used for setting up handicap and such
    if 'AB' in cursor.node.keys():
        for move in cursor.node['AB'].data:
            leela.add_move('black', move)

    if 'AW' in cursor.node.keys():
        for move in cursor.node['AW'].data:
            leela.add_move('white', move)

    return this_move
