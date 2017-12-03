"""
This is config template with default values.
Please rename/copy this file to 'config.py', if you don't have one.
"""

# Set verbosity level: 0: progress, 1: progress+status, 2: progress+status+state, 3: progress+status+state+stdout+stderr
verbosity = 0

# Common config
path_to_leela = './bots/leela/leela_0110_linux_x64_opencl'
analyze_time = 30
variations_time = 7
variations_depth = 2


checkpoint_dir = './.leela_checkpoints'
skip_checkpoints = False
path_to_log = './leela.log'

# Set time
analyze_threshold = 0.05
variations_threshold = 0.075

# Display winrate in progress bar on moves with delta more than analyze_threshold
show_winrate = True

move_list_threshold = 0.2  # Default is 0.15 (experimental)
num_to_show = 7

# Set range of moves to analyze
analyze_start = 0
analyze_end = float('inf')

# For leela setting, review its docs
leela_settings = ['--gtp', '--noponder']

