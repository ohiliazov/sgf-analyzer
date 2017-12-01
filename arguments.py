import os
import argparse


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

defaults = {
    'analyze_threshold':    0.05,   # Display analysis on moves losing approx at least this much win-rate
    'variations_threshold': 0.05,   # Explore variations on moves losing approx at least this much win-rate
    'analyze_time':         10,     # How many seconds to use per game move analysis?
    'variations_time':      30,     # How many seconds to use per variations analysis?
    'nodes_per_variation':  5,      # How many nodes to explore in each variation tree
    'num_to_show':          0,      # Number of moves to show from the sequence of suggested moves

    'win_graph':            False,  # Build pdf graph of win rate, must have matplotlib installed
    'wipe_comments':        False,  # Remove existing comments from the main line of the SGF file

    'analyze_start':        0,      # Analyze game from given move
    'analyze_end':          1000,   # Analyze game till given move
    'verbosity':            0,      # Set the verbosity level, 0: progress, 1: progress+status, 2: progress+status+state

    'restarts':             1,      # Number of restarts when bots crashes
    'stdev':                0.22,   # Default standard deviation
    'skip_white':           False,  # Skip analysis of white
    'skip_black':           False,  # Skip analysis of black
    'skip_checkpoints':     False,  # Skip existing checkpoints
    'log_to_file':          False,  # Log all input/output to file
    'ckpt_dir': os.path.expanduser('~/.leela_checkpoints'),  # Path to directory to cache partially complete analyses
}


parser = argparse.ArgumentParser()
required = parser.add_argument_group('required named arguments')

parser.add_argument("SGF_FILE",
                    help="SGF file to analyze")

parser.add_argument("--save_to_file",
                    dest='save_to_file',
                    help="File to save results of analyze, if skipped - use source filename with adding 'analyzed'")

required.add_argument('--leela',
                      required=True,
                      dest='executable',
                      metavar="CMD",
                      help="Command to run Leela executable")

parser.add_argument('--analyze-thresh',
                    dest='analyze_threshold',
                    default=defaults['analyze_threshold'],
                    type=float,
                    metavar="T",
                    help="Display analysis on moves losing approx at least this much "
                         "win rate when the game is close")

parser.add_argument('--var-thresh',
                    dest='variations_threshold',
                    default=defaults['variations_threshold'],
                    type=float,
                    metavar="T",
                    help="Explore variations on moves losing approx at least this much "
                         "win rate when the game is close")

parser.add_argument('--analyze-time',
                    dest='analyze_time',
                    default=defaults['analyze_time'],
                    type=int,
                    metavar="S",
                    help="How many seconds to use per move analysis")

parser.add_argument('--vars-time',
                    dest='variations_time',
                    default=defaults['variations_time'],
                    type=int,
                    metavar="S",
                    help="How many seconds to use per variation analysis")

parser.add_argument('--nodes-per-var',
                    dest='nodes_per_variation',
                    default=defaults['nodes_per_variation'],
                    type=int,
                    metavar="N",
                    help="How many nodes to explore with leela in each variation tree (default=8)")

parser.add_argument('--num_to_show',
                    dest='num_to_show',
                    default=defaults['num_to_show'],
                    type=int,
                    help="Number of moves to show from the sequence of suggested moves (default=0)")

parser.add_argument('--win-graph',
                    dest='win_graph',
                    default=defaults['win_graph'],
                    action='store_true',
                    help="Build pdf graph of win rate, must have matplotlib installed")

parser.add_argument('--wipe-comments',
                    dest='wipe_comments',
                    default=defaults['wipe_comments'],
                    action='store_true',
                    help="Remove existing comments from the main line of the SGF file")

parser.add_argument('--start',
                    dest='analyze_start',
                    default=defaults['analyze_start'],
                    type=int,
                    metavar="MOVENUM",
                    help="Analyze game starting at this move (default=0)")

parser.add_argument('--stop',
                    dest='analyze_end',
                    default=defaults['analyze_end'],
                    type=int,
                    metavar="MOVENUM",
                    help="Analyze game stopping at this move (default=1000)")

parser.add_argument('-v', '--verbosity',
                    default=defaults['verbosity'],
                    type=int,
                    metavar="V",
                    help="Set the verbosity level, 0: progress only, 1: progress+status, 2: progress+status+state")

parser.add_argument('--cache',
                    dest='ckpt_dir',
                    metavar="DIR",
                    default=defaults['ckpt_dir'],
                    help="Set a directory to cache partially complete analyses, default ~/.leela_checkpoints")

parser.add_argument('--restarts',
                    default=defaults['restarts'],
                    type=int,
                    metavar="N",
                    help="If leela crashes, retry the analysis step this many times before reporting a failure")

parser.add_argument('--skip-white',
                    dest='skip_white',
                    default=defaults['skip_white'],
                    action='store_true',
                    help="Do not display analysis or explore variations for white mistakes")

parser.add_argument('--skip-black',
                    dest='skip_black',
                    default=defaults['skip_black'],
                    action='store_true',
                    help="Do not display analysis or explore variations for black mistakes")

parser.add_argument('--skip-checkpoints',
                    dest='skip_checkpoints',
                    default=defaults['skip_checkpoints'],
                    action='store_true',
                    help="Do not use existing checkpoints. Mostly used for debug purpose.")

parser.add_argument('--log',
                    dest='log_to_file',
                    default=defaults['log_to_file'],
                    action='store_true',
                    help="Save all input/output into log file.")
