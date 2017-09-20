import os

# For leela setting, review its docs
leela_settings = [
    '--gtp',
    '--noponder'
]

# For ray setting, review its docs
ray_settings = [
    '--playout 100000',
    '--const-time 15',
    '--thread 4'
]

settings = {
    'seconds_per_search': 15,  # How many seconds to use per search?
    'analyze_threshold': 0.050,  # Display analysis on moves losing approx at least this much winrate
    'variations_threshold': 0.050,  # Explore variations on moves losing approx at least this much winrate
    'nodes_per_variation': 3,  # How many nodes to explore in each variation tree
    'num_to_show': 0,  # Number of moves to show from the sequence of suggested moves
    'win_graph': False,  # Build pdf graph of win rate, must have matplotlib installed
    'wipe_comments': False,  # Remove existing comments from the main line of the SGF file
    'analyze_start': 0,  # Analyze game from given move
    'analyze_end': 1000,  # Analyze game till given move
    'verbosity': 0,  # Verbosity
    'restarts': 1,  # Number of restarts when bots crashes
    'ckpt_dir': os.path.expanduser('~/.leela_checkpoints'),  # Path to directory to cache partially complete analyses
    'skip_white': False,  # Skip analysis of white
    'skip_black': False   # Skip analysis of black
}
