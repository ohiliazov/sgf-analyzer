import logging

# 0: progress only, 1: progress+status, 2: progress+status+state

gtp_logger = logging.getLogger('simple_example')
gtp_logger.setLevel(logging.DEBUG)

# create file handler which logs even debug messages
fh = logging.FileHandler('logs/gtp_console.log')
fh.setLevel(logging.DEBUG)

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s %(levelname)s : %(module)s - %(funcName)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)

# add the handlers to logger
gtp_logger.addHandler(ch)
gtp_logger.addHandler(fh)
