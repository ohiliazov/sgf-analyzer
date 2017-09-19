import os

defaults = {
    'leela_executable': "Leela0110GTP.exe",
    'save_to_file': sgfanalyze.args.SGF_FILE.split('.')[0] + '_analyzed.sgf',

    # Display analysis on moves losing approx at least this much win rate when the game is close
    'analyze_threshold': 0.050,
    # Explore variations on moves losing approx at least this much win rate when the game is close
    'variations_threshold': 0.050,
    # How many seconds to use per search?
    'seconds_per_search': 15,
    # How many nodes to explore in each variation tree
    'nodes_per_variation': 3,
    # Number of moves to show from the sequence of suggested moves
    'num_to_show': 3,
    # Build pdf graph of win rate, must have matplotlib installed
    'win_graph': False,
    # Remove existing comments from the main line of the SGF file
    'wipe_comments': False,
    # Analyze game starting from one move till another move
    'analyze_start': 0,
    'analyze_end': 1000,
    # Verbosity
    'verbosity': 0,
    # Number of restarts when bots crashes
    'restarts': 1,
    # Path to directory to cache partially complete analyses
    'ckpt_dir': os.path.expanduser('~/.leela_checkpoints'),
    # Skip analysis of white and black
    'skip_white': False,
    'skip_black': False
}

# For ray setting, review its docs
ray_settings = [
    '--playout 100000',
    '--const-time 15',
    '--thread 4',

]
