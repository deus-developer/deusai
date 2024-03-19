import functools
import logging

from core import InnerUpdate


def log(func):
    """Logs at debug level entering, result and exiting for decorated method"""
    logger = logging.getLogger(func.__module__)

    @functools.wraps(func)
    def decorator(self, *args, **kwargs):
        logger.debug('Entering: %s', func.__name__)
        result = func(self, *args, **kwargs)
        logger.debug(result)
        logger.debug('Exiting: %s', func.__name__)
        return result

    return decorator


def log_command(func):
    """Logs at info level entering, that a command has been invoked by user"""
    logger = logging.getLogger(func.__module__)

    @functools.wraps(func)
    def decorator(self, update: InnerUpdate, *args, **kwargs):
        user = update.invoker
        command = update.command
        if command and command.is_valid() and user:
            logger.info(f'Command "{command}" invoked by #{user.user_id}')
        result = func(self, update, *args, **kwargs)
        return result

    return decorator
