import functools
import logging
import time

from core import Update
from models import LeadTime


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
    def decorator(self, update: Update, *args, **kwargs):
        user = update.invoker
        command = update.command
        if command and command.is_valid() and user:
            logger.info(f'Command "{command}" invoked by #{user.user_id}')
        result = func(self, update, *args, **kwargs)
        return result

    return decorator


def lead_time(name: str, description: str):
    def wrapper(func):
        logger = logging.getLogger(func.__module__)

        @functools.wraps(func)
        def decorator(self, update: Update, *args, **kwargs):
            start_time = time.time()
            result = func(self, update, *args, **kwargs)
            end_time = time.time()

            LeadTime.create(
                executor=update.invoker,
                start_time=start_time,
                end_time=end_time,
                name=name,
                description=description,
                update=update.to_json()
            )
            return result

        return decorator

    return wrapper
