# Path to executables
path_to_leela = './bots/leela/leela_0110_linux_x64'
path_to_zero = None
path_to_aq = None
path_to_ray = None

# Set verbosity level: 0: progress, 1: progress+status, 2: progress+status+state, 3: progress+status+state+stdout+stderr
verbosity = 0

# MOVES TO ANALYZE
analyze_start = 0
analyze_end = float('inf')

# TIME SETTINGS
analyze_time = 5
variations_time = 5

# THRESHOLDS AND DEPTH OF ANALYSIS
analyze_threshold = 0.05    # Displays analysis data to moves with at least this winrate drop.
variations_threshold = 0.1  # Analyzes moves with at least this winrate drop
variations_depth = 3        # How deep the move should be analyzed?
num_to_show = 7             # How many moves to show from perfect variation

# MISCELLANEOUS
checkpoint_dir = './.leela_checkpoints'
skip_checkpoints = False
show_winrate = True
restarts = 0

# DO NOT CHANGE IF UNSURE
move_list_threshold = 0.15  # This filters suggested move list by at least this probability
