## Leela Analysis Script

This script is a modified version of scripts originally from:
https://github.com/lightvector/leela-analysis

Currently, it's designed to work with Leela 0.10.0, no guarantees about compatibility with any past or future versions. It runs on python3.

WARNING: It is not uncommon for Leela to mess up on tactical situations and give poor suggestions, particularly when it hasn't
realized the life or death of a group yet that is actually already alive or dead. Like all MC bots, it also has a somewhat different
notion than humans of how to wrap up a won game and what moves (despite still being winning) are "mistakes". Take the analysis with
many grains of salt.

### How to Use
First, download and install the "engine only"/"commandline"/"GTP" version of Leela 0.10.0 from:
https://sjeng.org/leela.html

Clone this repository to a local directory:

    git clone https://github.com/lightvector/leela-analysis
    cd leela-analysis

Then simply run the script to analyze a game, providing the command to run to the leela executable, such as ./Leela0100GTP.exe or ./leela_0100_linux_x64.

    sgfanalyze.py my_game.sgf --leela /PATH/TO/LEELA.exe > my_game_analyzed.sgf

By default, Leela will go through every position in the provided game and find what it considers to be all the mistakes by both players,
producing an SGF file where it highlights those mistakes and provides alternative variations it would have expected. It will probably take
an hour or two to run.

Run the script with --help to see other options you can configure. You can change the amount of time Leela will analyze for, change how
much effort it puts in to making variations versus just analyzing the main game, or select just a subrange of the game to analyze.

### Troubleshooting

If you get an "OSError: [Errno 2] No such file or directory" error or you get an "OSError: [Errno 8] Exec format error" originating from "subprocess.py",
check to make sure the command you provided for running Leela is correct. The former usually happens if you provided the wrong path, the latter if
you provided the wrong Leela executable for your OS.

If get an error like "WARNING: analysis stats missing data" that causes the analysis to consistently fail at a particular spot in a given sgf file and only
output partial results, there is probably a bug in the script that causes it not to be able to parse a particular output by Leela in that position. Feel
free to open an issue and provide the SGF file that causes the failure. You can also run with "-v 3" to enable super-verbose output and see exactly what
Leela is outputting on that position.
