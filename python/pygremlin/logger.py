# coding: utf-8
import logging

# This is the default logger with no output
logger = logging.getLogger('pygremlin')
logger.addHandler(logging.NullHandler())

def configure_debug():
    """
    Default logging configuration with debug ouput
    :return: logger instance
    """
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(filename)s %(levelname)s:"
                                      " %(message)s"))

    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)
    return logger

__all__ = ['logger', 'configure_debug']