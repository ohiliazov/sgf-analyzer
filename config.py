"""
This is config template with default values.
Please rename/copy this file to 'config.py', if you don't have one.
"""

# Set verbosity level: 0: progress, 1: progress+status, 2: progress+status+state, 3: progress+status+state+stdout+stderr
verbosity = 0

# Common config
path_to_leela = './bots/leela/leela_0110_linux_x64_opencl'
analyze_time = 20
variations_time = 10
variations_depth = 5


checkpoint_dir = './.leela_checkpoints'
skip_checkpoints = False
path_to_log = './leela.log'

# Set time
analyze_threshold = 0.05
variations_threshold = 0.1

# Display winrate in progress bar on moves with delta more than analyze_threshold
show_winrate = True

num_to_show = 7

# Set range of moves to analyze
analyze_start = 0
analyze_end = float('inf')

# For leela setting, review its docs
leela_settings = ['--gtp', '--noponder']

move_list_threshold = 0.15  # Default is 0.2 (experimental)
restarts = 5
