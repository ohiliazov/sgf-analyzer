## Leela Analysis Script

This script is a modified version of scripts originally from:
https://github.com/lightvector/leela-analysis

Currently, it's designed to work with **Leela 0.10.0**, no guarantees about compatibility with any past or future versions. 
It runs on Python 3.

**WARNING:** It is not uncommon for Leela to mess up on tactical situations and give poor suggestions, particularly when it hasn't
realized the life or death of a group yet that is actually already alive or dead. Like all MC bots, it also has a somewhat different
notion than humans of how to wrap up a won game and what moves (despite still being winning) are "mistakes". Take the analysis with
many grains of salt.

### How to Use
First, download and install the commandline/GTP engine version of Leela from:

    https://sjeng.org/leela.html

Download or Clone this repository to a local directory:

    git clone https://github.com/jumpman24/leela-analysis-36
    cd leela-analysis-36

Then run the script to analyze a game, providing the command with arguments:
* file name of game to analyze 
* path to GTP version of Leela, such as ./Leela0100GTP.exe or ./leela_0100_linux_x64, etc.
* other parameters are optional
    
      sgfanalyze.py my_game.sgf --leela /PATH/TO/LEELA.exe

Some of available options:

    --analyze-time    - How many seconds to use per game moves analysis (default=30)
    --variations-time - How many seconds to use per variations analysis (default=15)
    --var-thresh      - Explore variations on moves losing at least this much of win rate (default=0.03)
    --analyze-thresh  - Display analysis on moves losing at least this much of win rate (default=0.03)    
    --nodes-per-var   - Number of nodes to explore (depth) in each variation tree (default=8)
    --num_to_show     - Number of moves to show in addition to nodes-per-var, 
                        helps to clean-up irrational variations (default=0) 
    --wipe-comments   - Remove existing comments from the main line of the SGF file
    --no-graph        - Do not build nice pdf graph of win rate progress
    --verbosity       - Set the verbosity level

By default, Leela will go through every position in the provided game and find what it considers to be all the mistakes by both players,
producing an SGF file where it highlights those mistakes and provides alternative variations it would have expected. It will probably take
an hour or two to run.

Run the script with --help to see other options you can configure. You can change the amount of time Leela will analyze for, change how
much effort it puts in to making variations versus just analyzing the main game, or select just a subrange of the game to analyze.
___

### TODO list:

   - [x] clean-up suggested variations with low visits rate
   - [ ] mark by A-B alternatives which has low difference
   - [ ] support Ray bot (in progress) 
   - [ ] code refactoring (in progress) 
   - [ ] add documentation (in progress) 
   - [ ] show even branches
   - [ ] add params to stop analysis if win rate drops > ~80%
   - [ ] add logger
   - [x] tune performance between leela calls
   - [x] support/clean-up non english characters (bug)
   - [x] update pdf graph output to have better look
   - [x] write to file during analysis
   - [x] write to file with Python 3 instead of console
   - [x] add limitation to show suggested moves
   - [x] add config file
   - [x] divided time for move and variations analysis

___

### Troubleshooting

If you get an "OSError: [Errno 2] No such file or directory" error or you get an "OSError: [Errno 8] Exec format error" originating from "subprocess.py",
check to make sure the command you provided for running Leela is correct. The former usually happens if you provided the wrong path, the latter if
you provided the wrong Leela executable for your OS.

If get an error like "WARNING: analysis stats missing data" that causes the analysis to consistently fail at a particular spot in a given sgf file and only
output partial results, there is probably a bug in the script that causes it not to be able to parse a particular output by Leela in that position. Feel
free to open an issue and provide the SGF file that causes the failure. You can also run with "-v 3" to enable super-verbose output and see exactly what
Leela is outputting on that position.
