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


def calculate_tasks_left(sgf, comment_requests_analyze, comment_requests_variations, args):
    cursor = sgf.cursor()
    move_num = 0
    analyze_tasks = 0
    variations_tasks = 0
    while not cursor.atEnd:
        cursor.next()

        analysis_mode = None
        if args.analyze_start <= move_num <= args.analyze_end:
            analysis_mode = 'analyze'

        if move_num in comment_requests_analyze or (move_num - 1) in comment_requests_analyze or (
                move_num - 1) in comment_requests_variations:
            analysis_mode = 'analyze'

        if move_num in comment_requests_variations:
            analysis_mode = 'variations'

        if analysis_mode == 'analyze':
            analyze_tasks += 1
        elif analysis_mode == 'variations':
            analyze_tasks += 1
            variations_tasks += 1

        move_num += 1
    return analyze_tasks, variations_tasks
