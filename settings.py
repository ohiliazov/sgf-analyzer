import os

BASE_DIR = os.path.abspath(os.path.curdir)
BOTS_DIR = os.path.join(BASE_DIR, 'bots')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
CHECKPOINTS_DIR = os.path.join(BASE_DIR, '.checkpoints', '{}')

PATH_TO_CONFIG = os.path.abspath(os.path.join(BASE_DIR, 'config.yaml'))
