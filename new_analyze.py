import argparse
import hashlib
import os
import settings

from yaml import load

from log import logger
from CLI.leela import Leela, LeelaZero
from sgflib import SGFParser


class Bot(object):
    def factory(self, bot):
        with open(settings.PATH_TO_CONFIG) as y:
            bot_settings = load(y).get('bot_settings', {}).get(bot)

            if bot_settings['type'] == 'leela':
                return Leela(**bot_settings)
            if bot_settings['type'] == 'leela-zero':
                return LeelaZero(**bot_settings)

        logger.error("Config %s not found.", bot)


def parse_cmd_line():
    parser = argparse.ArgumentParser()

    parser.add_argument(dest="path_to_sgf",
                        nargs='+',
                        help="SGF file to analyze")

    parser.add_argument('-b', '--bot',
                        default='leela',
                        dest='bot',
                        metavar="CMD",
                        help="Config")

    return parser.parse_args()


def parse_sgf_file(path_to_sgf):
    """Return parsed Collection from sgf"""
    with open(path_to_sgf, 'r', encoding="utf-8") as sgf_file:
        data = "".join([line for line in sgf_file])
    return SGFParser(data).parse()


def make_checkpoint_dir(sgf, bot):
    """Create unique checkpoint directory"""
    base_hash = hashlib.md5(str(sgf).encode()).hexdigest()
    base_dir = os.path.join(settings.CHECKPOINTS_DIR.format(bot), base_hash)
    os.makedirs(base_dir, exist_ok=True)

    return base_dir


def analyze_game(game, bot):
    logger.info("Started analyzing file: %s", os.path.basename(game))
    sgf = parse_sgf_file(game)
    base_dir = make_checkpoint_dir(sgf, bot)
    logger.info("Finished analyzing file: %s", os.path.basename(game))


if __name__ == '__main__':
    cmd_args = parse_cmd_line()

    games = []
    for path in cmd_args.path_to_sgf:
        if os.path.isdir(path):
            for file in os.listdir(path):
                path_to_file = os.path.join(path, file)
                if os.path.splitext(path_to_file)[1] == '.sgf':
                    games.append(path_to_file)
        elif os.path.exists(path):
            games.append(path)

    logger.info('Found %s sgf-files to analyze.', len(games))

    for game in games:
        analyze_game(game, cmd_args.bot)

    logger.info('Analysis done for %s sgf-files.', len(games))
