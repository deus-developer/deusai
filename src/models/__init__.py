from .base import BaseModel, database
from .group import Group, GroupPlayerThrough, GroupLiderThrough
from .player import Player, PlayerStatHistory
from .radar import Radar
from .raid_assign import RaidAssign, RaidStatus
from .raids_interval import RaidsInterval
from .settings import Settings
from .telegram_chat import TelegramChat
from .telegram_user import TelegramUser
from .trigger import Trigger

MODELS = {
    TelegramUser,
    TelegramChat,
    Player,
    PlayerStatHistory,
    Group,
    GroupPlayerThrough,
    GroupLiderThrough,
    RaidAssign,
    Radar,
    Settings,
    Trigger,
    RaidsInterval,
}

with database:
    database.create_tables(MODELS)
