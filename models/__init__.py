from .base import BaseModel, database
from .karma_transition import KarmaTransition
from .raid_result import RaidResult
from .settings import Settings
from .telegram_chat import TelegramChat
from .telegram_user import TelegramUser
from .raids_interval import RaidsInterval
from .pig import Pig, PigFight

from .player import Player, PlayerStatHistory, PlayerRecivedThrough, PlayerSendedThrough
from .group import Group, GroupPlayerThrough, GroupLiderThrough
from .radar import Radar
from .raid_assign import RaidAssign, RaidStatus
from .shop import SPItem, SPProcess
from .shop2 import ShopItem, ShopPurchase, Auction, AuctionMember
from .trigger import Trigger

MODELS = {
    TelegramUser,
    TelegramChat,
    Player,
    Pig,
    PigFight,
    PlayerStatHistory,
    Group,
    GroupPlayerThrough,
    GroupLiderThrough,
    RaidAssign,
    RaidResult,
    Radar,
    KarmaTransition,
    PlayerRecivedThrough,
    PlayerSendedThrough,
    SPItem,
    SPProcess,
    Settings,
    Trigger,
    RaidsInterval,
    ShopItem,
    ShopPurchase,
    Auction,
    AuctionMember
}

with database:
    database.create_tables(MODELS)
