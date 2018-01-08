import argparse
import config

parser = argparse.ArgumentParser()

parser.add_argument("path_to_sgf",
                    help="SGF file to analyze")

parser.add_argument('--use-console',
                    default='leela',
                    dest='gtp_console',
                    metavar="CMD",
                    help="Command to run Leela executable")

parser.add_argument('--leela',
                    default=config.path_to_leela,
                    dest='path_to_leela',
                    metavar="CMD",
                    help="Command to run Leela executable")

parser.add_argument('--leela-zero',
                    default=config.path_to_leela_zero,
                    dest='path_to_leela_zero',
                    metavar="CMD",
                    help="Command to run LeelaZero executable")

parser.add_argument('--analyze-time',
                    dest='analyze_time',
                    default=config.analyze_time,
                    type=int,
                    help="How many seconds to use per move analysis")

parser.add_argument('--variations-time',
                    dest='variations_time',
                    default=config.variations_time,
                    type=int,
                    help="How many seconds to use per variation analysis")

parser.add_argument('--analyze-thresh',
                    dest='analyze_threshold',
                    default=config.analyze_threshold,
                    type=float,
                    help="Display analysis on moves losing approx at least this much "
                         "win rate when the game is close")

parser.add_argument('--var-thresh',
                    dest='variations_threshold',
                    default=config.variations_threshold,
                    type=float,
                    help="Explore variations on moves losing approx at least this much "
                         "win rate when the game is close")

parser.add_argument('--nodes-per-var',
                    dest='variations_depth',
                    default=config.variations_depth,
                    type=int,
                    help="How many nodes to explore with leela in each variation tree (default=8)")

parser.add_argument('--num_to_show',
                    dest='num_to_show',
                    default=config.num_to_show,
                    type=int,
                    help="Number of moves to show from the sequence of suggested moves (default=0)")

parser.add_argument('--no-graph',
                    dest='win_graph',
                    action='store_false',
                    help="Do not build pdf graph of win rate, graph requires matplotlib installed")

parser.add_argument('--wipe-comments',
                    dest='wipe_comments',
                    action='store_true',
                    help="Remove existing comments from the main line of the SGF file")

parser.add_argument('--start',
                    dest='analyze_start',
                    default=config.analyze_start,
                    type=int,
                    help="Analyze game starting at this move (default=0)")

parser.add_argument('--stop',
                    dest='analyze_end',
                    default=config.analyze_end,
                    type=int,
                    help="Analyze game stopping at this move (default=infinity)")

parser.add_argument('--skip-white',
                    dest='skip_white',
                    action='store_true',
                    help="Do not display analysis or explore variations for white mistakes")

parser.add_argument('--skip-black',
                    dest='skip_black',
                    action='store_true',
                    help="Do not display analysis or explore variations for black mistakes")

parser.add_argument('--winrate',
                    dest='show_winrate',
                    default=config.show_winrate,
                    action='store_true',
                    help="Display winrate in progress bar")
