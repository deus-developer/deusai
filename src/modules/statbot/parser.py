from typing import Optional

import telegram
from telegram.ext import MessageHandler, Dispatcher
from telegram.ext.filters import Filters

from src.core import EventManager, MessageManager, InnerUpdate
from src.decorators.update import inner_update
from src.decorators.users import get_player
from src.modules import BasicModule
from src.utils.functions import CustomFilters
from src.wasteland_wars.parsers import (
    parse_pipboy,
    parse_gang_panel,
    parse_goat_panel,
    parse_raid_reward,
    parse_showdata,
)
from src.wasteland_wars.schemas import (
    Profile,
    GangPanel,
    GoatPanel,
    RaidReward,
    ShowData,
)


class PlayerParseResult(InnerUpdate):
    def __init__(self, update: telegram.Update):
        super().__init__(update)

        self.raid: Optional[RaidReward] = None
        self.profile: Optional[Profile] = None
        self.showdata: Optional[ShowData] = None


class GroupParseResult(InnerUpdate):
    def __init__(self, update: telegram.Update):
        super(GroupParseResult, self).__init__(update)

        self.gang: Optional[GangPanel] = None
        self.goat: Optional[GoatPanel] = None


class ParserModule(BasicModule):
    """
    responds to forwards in group 1 (not default 10 and not activity 0)
    as a result make EventManager trigger WWHandlers in other modules
    """

    module_name = "parser"
    group = 1

    def __init__(
        self,
        event_manager: EventManager,
        message_manager: MessageManager,
        dispatcher: Dispatcher,
    ):
        self.add_handler(MessageHandler(CustomFilters.ww_forwarded & Filters.text, self._text))

        super().__init__(event_manager, message_manager, dispatcher)

    @inner_update(PlayerParseResult)
    @get_player
    def _text(self, update: PlayerParseResult):
        message = update.telegram_update.message
        if message.text is None:
            return

        player_info_parsed = update

        player_info_parsed.profile = parse_pipboy(message)
        player_info_parsed.raid = parse_raid_reward(message)
        player_info_parsed.showdata = parse_showdata(message)

        group_info_parsed = GroupParseResult(update.telegram_update)
        group_info_parsed.invoker = player_info_parsed.invoker
        group_info_parsed.player = player_info_parsed.player

        group_info_parsed.gang = parse_gang_panel(message)
        group_info_parsed.goat = parse_goat_panel(message)

        self.event_manager.invoke_handler_update(player_info_parsed)
        self.event_manager.invoke_handler_update(group_info_parsed)
