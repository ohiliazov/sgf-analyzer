# Path to executables
path_to_leela = './bots/leela/leela_0110_linux_x64_opencl'
path_to_leela_zero = '/home/gelya/PycharmProjects/leela-zero/src/leelaz'
path_to_leela_zero_weights = './bots/weights.txt'
path_to_aq = None
path_to_ray = None

# MOVES TO ANALYZE
analyze_start = 1
analyze_end = float('inf')

# TIME SETTINGS
analyze_time = 60
variations_time = 30
playouts = 50000

# THRESHOLDS AND DEPTH OF ANALYSIS
analyze_threshold = 0.05    # Displays analysis data to moves with at least this winrate drop.
variations_threshold = 0.1  # Analyzes moves with at least this winrate drop
variations_depth = 3        # How deep the move should be analyzed?
num_to_show = float('inf')  # How many moves to show from perfect variation

# MISCELLANEOUS
skip_checkpoints = False
show_winrate = True
restarts = 0

# DO NOT CHANGE IF UNSURE
move_list_threshold = 0.2  # This filters suggested move list by at least this probability
move_list_max_length = 3   # LeelaZero option. Change this to float('inf') if you want full output (not recommended).
stop_on_winrate = 0.8      # Here you can stop the analysis if winrate of either side is more than this
