import datetime
import logging.config
import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())
BASEDIR = os.path.dirname(__file__)


class ImproperlyConfigured(Exception):
    """Something is somehow improperly configured"""


class Config(object):
    """Base class for app configuration"""
    DEBUG = False
    TESTING = False

    DATABASE_URL = os.getenv('DATABASE_URL',
                             'sqlite:///' + os.path.join(BASEDIR, 'db.sqlite'))
    # LEGACY_DATABASE_PATH = os.getenv('LEGACY_DB_PATH', 'db.sqlite')

    TG_TOKEN = os.getenv('TG_TOKEN')

    TG_PROXY_URL = os.getenv('TG_PROXY_URL')

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
            'handlers': {
                'default': {
                    'level': self.LOG_LEVEL,
                    'formatter': 'standard',
                    'class': 'logging.StreamHandler',
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
            raise ImproperlyConfigured('You must set TG_TOKEN enviroment variable')

        self.ADMIN_CHAT_ID = int(self.ADMIN_CHAT_ID)
        self.GOAT_ADMIN_CHAT_ID = int(self.GOAT_ADMIN_CHAT_ID)
        self.CRM_SHOP_CHAT_ID = int(self.CRM_SHOP_CHAT_ID)
        self.UNKOWN_CHAT_ID = int(self.UNKOWN_CHAT_ID)
        self.NOTIFY_CHAT_ID = int(self.NOTIFY_CHAT_ID)

        self.BASEDIR = BASEDIR

        logging.config.dictConfig(self.LOGGING_CONFIG)
        logger = logging.getLogger('apscheduler.executors.default')
        logger.setLevel(logging.WARNING)


class DevelopmentConfig(Config):
    DEBUG = True


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
            'handlers': {
                'default': {
                    'level': self.LOG_LEVEL,
                    'formatter': 'standard',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': os.path.join(BASEDIR, 'logs', 'bot.log'),
                    'mode': 'a',
                    'maxBytes': 1 << 20,  # 1M
                    'backupCount': 5,
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


_config_relation = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

ConfigClass = _config_relation[os.environ.get('BOT_CONFIG', 'default')]
settings = ConfigClass()
