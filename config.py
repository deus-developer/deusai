import logging.config
import os
import datetime
from dotenv import (
    find_dotenv,
    load_dotenv
)

load_dotenv(find_dotenv())
BASEDIR = os.path.dirname(__file__)


class ImproperlyConfigured(Exception):
    """Something is somehow improperly configured"""


class HideTokenFilter(logging.Filter):
    """Logging filter that replaces telegram token with ********"""

    def __init__(self, token):
        super(HideTokenFilter, self).__init__()
        self._token = token

    def filter(self, record):
        record.msg = self._hide(record.msg)
        if isinstance(record.args, dict):
            for key in record.args.keys():
                record.args[key] = self._hide(record.args[key])
        else:
            record.args = tuple(self._hide(arg) for arg in record.args)
        return True

    def _hide(self, msg):
        if isinstance(msg, str):
            return msg.replace(self._token, '********')
        return msg


class Config(object):
    """Base class for app configuration"""
    DEBUG = False
    TESTING = False

    DATABASE_URL = os.getenv(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(BASEDIR, 'db.sqlite')
        )

    TG_TOKEN = os.getenv('TG_TOKEN')

    ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

    GOAT_ADMIN_CHAT_ID = os.getenv('GOAT_ADMIN_CHAT_ID', ADMIN_CHAT_ID)
    CRM_SHOP_CHAT_ID = os.getenv('CRM_SHOP_CHAT_ID', ADMIN_CHAT_ID)
    UNKOWN_CHAT_ID = os.getenv('UNKOWN_CHAT_ID', ADMIN_CHAT_ID)
    NOTIFY_CHAT_ID = os.getenv('NOTIFY_CHAT_ID', ADMIN_CHAT_ID)

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    DATETIME_FORMAT = os.getenv('DATETIME_FORMAT', '%Y-%m-%d %H:%M:%S')
    timezone = datetime.timezone(offset=datetime.timedelta(hours=3))  # MSK

    @property
    def LOGGING_CONFIG(self):
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format':
                        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
            },
            'filters': {
                'hidetoken': {
                    '()': HideTokenFilter,
                    'token': self.TG_TOKEN
                }
            },
            'handlers': {
                'default': {
                    'level': self.LOG_LEVEL,
                    'formatter': 'standard',
                    'class': 'logging.StreamHandler',
                    'filters': [
                        'hidetoken',
                    ],
                },
            },
            'loggers': {
                '': {
                    'handlers': ['default'],
                    'level': self.LOG_LEVEL,
                    'propagate': True
                }
            }
        }

    def __init__(self):
        if not self.TG_TOKEN:
            raise ImproperlyConfigured(
                'You must set TG_TOKEN enviroment variable'
            )
        try:
            self.ADMIN_CHAT_ID = int(self.ADMIN_CHAT_ID)
        except ValueError:
            raise ImproperlyConfigured('ADMIN_CHAT_ID must be integer')
        try:
            self.GOAT_ADMIN_CHAT_ID = int(self.GOAT_ADMIN_CHAT_ID)
        except ValueError:
            raise ImproperlyConfigured('GOAT_ADMIN_CHAT_ID must be integer')

        try:
            self.CRM_SHOP_CHAT_ID = int(self.CRM_SHOP_CHAT_ID)
        except ValueError:
            self.CRM_SHOP_CHAT_ID = self.ADMIN_CHAT_ID

        try:
            self.UNKOWN_CHAT_ID = int(self.UNKOWN_CHAT_ID)
        except ValueError:
            self.UNKOWN_CHAT_ID = self.ADMIN_CHAT_ID

        try:
            self.NOTIFY_CHAT_ID = int(self.NOTIFY_CHAT_ID)
        except ValueError:
            self.NOTIFY_CHAT_ID = self.ADMIN_CHAT_ID

        self.sql_logging = True if self.sql_logging == '1' else False
        self.BASEDIR = BASEDIR
        logging.config.dictConfig(self.LOGGING_CONFIG)
        logger = logging.getLogger('apscheduler.executors.default')
        logger.setLevel(logging.WARNING)


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DATABASE_URL = os.environ.get('TEST_DATABASE_URL') or 'sqlite:///:memory:'


class ProductionConfig(Config):
    DEBUG = False

    @property
    def LOGGING_CONFIG(self):
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format':
                        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                },
            },
            'filters': {
                'hidetoken': {
                    '()': HideTokenFilter,
                    'token': self.TG_TOKEN
                }
            },
            'handlers': {
                'default': {
                    'level': self.LOG_LEVEL,
                    'formatter': 'standard',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': os.path.join(BASEDIR, 'logs', 'bot.log'),
                    'mode': 'a',
                    'maxBytes': 1 << 20,  # 1M
                    'backupCount': 5,
                    'filters': [
                        'hidetoken',
                    ],
                },
            },
            'loggers': {
                '': {
                    'handlers': ['default'],
                    'level': self.LOG_LEVEL,
                    'propagate': True
                }
            }
        }


class HerokuConfig(Config):
    DEBUG = False
    TESTING = False


# При инициализации бота должно указываться название запускаемой конфигурации,
#   либо по умолчанию будет режим dev
_config_relation = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'heroku': HerokuConfig,
    'default': DevelopmentConfig
}

ConfigClass = _config_relation[os.environ.get('BOT_CONFIG', 'default')]
settings = ConfigClass()
