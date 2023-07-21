import sys
import os
import logging
import logging.handlers

from . import CoreConstants

__loggers__ : set[str] = set()

def create_setup_logger(name: str = None, log_file: str = "", log_level=logging.DEBUG):

    logger = logging.getLogger(name)

    logger.setLevel(log_level)

    if name in __loggers__:
        return logger

    __loggers__.add(name)

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
        except:
            pass
        file_handler = logging.handlers.TimedRotatingFileHandler(log_file, 'midnight', 1,encoding='utf-8', backupCount=5)
        # file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)



    logger.addHandler(stdout_handler)

    return logger


def setup_logging(log_file: str = "", log_level=logging.DEBUG):
    create_setup_logger(log_file=log_file, log_level=log_level)
    create_setup_logger(CoreConstants.BRAND, log_file, log_level)


def add_unhandled_exception_hook(replace=False):

    def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        if not replace:
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_unhandled_exception
