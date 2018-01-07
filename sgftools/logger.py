import logging

# LOGGER FORMAT
formatter = logging.Formatter('%(asctime)s [%(levelname)s]:  %(message)s')

gtp_logger = logging.getLogger('gtp_console')
gtp_logger.setLevel(logging.DEBUG)
gtp_logger_file = logging.FileHandler('logs/gtp_console.log')
gtp_logger_file.setLevel(logging.DEBUG)
gtp_logger_file.setFormatter(formatter)
gtp_logger.addHandler(gtp_logger_file)

analyzer_logger = logging.getLogger('analyzer')
analyzer_logger.setLevel(logging.DEBUG)
analyzer_logger_file = logging.FileHandler('logs/analyzer.log')
analyzer_logger_file.setLevel(logging.DEBUG)
analyzer_logger_file.setFormatter(formatter)
analyzer_logger.addHandler(analyzer_logger_file)
