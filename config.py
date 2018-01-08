# Path to executables
path_to_leela = './bots/leela/leela_0110_linux_x64'
path_to_leela_zero = './bots/leela-zero/leelaz'
path_to_leela_zero_weights = './bots/leela-zero/weights.txt'
path_to_aq = None
path_to_ray = None

# MOVES TO ANALYZE
analyze_start = 140
analyze_end = 160

# TIME SETTINGS
analyze_time = 30
variations_time = 15
playouts = 50000

# THRESHOLDS AND DEPTH OF ANALYSIS
analyze_threshold = 0.05    # Displays analysis data to moves with at least this winrate drop.
variations_threshold = 0.1  # Analyzes moves with at least this winrate drop
variations_depth = 2        # How deep the move should be analyzed?
num_to_show = 7             # How many moves to show from perfect variation

# MISCELLANEOUS
checkpoint_dir = './.leela_checkpoints'
skip_checkpoints = False
show_winrate = True
restarts = 0

# DO NOT CHANGE IF UNSURE
move_list_threshold = 0.2  # This filters suggested move list by at least this probability
move_list_max_length = 3   # LeelaZero option. Change this to float('inf') if you want full output (not recommended).
