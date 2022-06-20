import logging
import os
import sys

from .settings import LOGS_DIR

fmt = logging.Formatter('%(asctime)-15s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('logs')
logger.setLevel(logging.DEBUG)

log_file = logging.FileHandler(os.path.join(LOGS_DIR, 'sgf-analyze.log'))
log_file.setLevel(logging.DEBUG)
log_stream = logging.StreamHandler(sys.stdout)
log_stream.setLevel(logging.INFO)

log_file.setFormatter(fmt)
log_stream.setFormatter(fmt)

logger.addHandler(log_file)
logger.addHandler(log_stream)
