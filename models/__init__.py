from .base import (
    BaseModel,
    database
)
from .telegram_user import TelegramUser
from .telegram_chat import TelegramChat
from .karma_transition import KarmaTransition
from .rank import Rank
from .settings import Settings
from .notebook import Notebook
from .player import (
    Player,
    PlayerStatHistory,
    PlayerRecivedThrough,
    PlayerSendedThrough
)
from .group import (
    Group,
    GroupPlayerThrough,
    GroupLiderThrough
)
from .raid_assign import (
    RaidAssign,
    RaidStatus
)
from .raid_result import RaidResult
from .radar import Radar
from .feedback import Feedback
from .shop import (
    SPItem,
    SPProcess
)
from .trigger import Trigger

from .item import (
    Item,
    InventoryItem
)
from .vote import (
    Vote,
    VoteAnswer,
    AnswerPlayerThrough
)
from .km_profit import KMProfit
from .lead_time import LeadTime
from .pvp import PVP
from .raids_interval import RaidsInterval

from .shop2 import (
    ShopItem,
    ShopPurchase,
    Auction,
    AuctionMember
)

MODELS = {
    TelegramUser, TelegramChat, Player, PlayerStatHistory,
    Group, GroupPlayerThrough, GroupLiderThrough, RaidAssign,
    RaidResult, Radar, Notebook, KarmaTransition, PlayerRecivedThrough,
    PlayerSendedThrough, Feedback, Rank,
    SPItem, SPProcess, Settings, Trigger, Vote, KMProfit, LeadTime,
    VoteAnswer, AnswerPlayerThrough, Item, InventoryItem, PVP,
    RaidsInterval, ShopItem, ShopPurchase, Auction, AuctionMember
}

with database:
    database.create_tables(MODELS)
