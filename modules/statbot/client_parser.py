import re

from telegram.ext import Dispatcher
from telegram.ext.dispatcher import run_async
from telethon.network import connection
from telethon.sync import TelegramClient, events, utils

from core import EventManager, MessageManager, Update as InnerUpdate
from modules import BasicModule
from models import TelegramUser
from ww6StatBotWorld import Wasteland

class TakingSuccess:
        gang_name: str
        location_name: str

        def __init__(self, match = None):
            if not match:
                self.gang_name, self.location_name = '[отсутствует]', '[подземелье]'
            else:
                self.gang_name, self.location_name = match.group('gang_name', 'location_name')

class DzenEnhancement:
        nickname: str
        fraction: str
        dzen: int

        def __init__(self, match = None):
            if not match:
                self.nickname, self.fraction, self.dzen = '[неизвестный]', '[fraction]', 0
            else:
                self.nickname = match.group('nickname')
                self.fraction = Wasteland.fractions_by_icon.get(match.group('fraction_icon'), match.group('fraction_icon'))
                self.dzen = int(match.group('dzen'))

class BossSpawn:
        boss_name: str

        def __init__(self, match = None):
            if not match:
                self.boss_name = '[Босс]'
            else:
                self.boss_name = match.group('boss_name')

class ClientParser(BasicModule):
    """
    start handler
    """
    module_name = 'client_parser'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        super().__init__(event_manager, message_manager)

        class Config(object):
            proxy_use = True
            proxy_url = 'proxy.digitalresistance.dog'
            proxy_port = 443
            proxy_secret = 'd41d8cd98f00b204e9800998ecf8427e'

            session_name = 'tolyly'
            app_id = 469206
            api_hash = 'd4fb5eb063ae4bc15932a5386123b607'

            # keeper = 'DeusDeveloper'
            keeper = 'tolyIya'

        self.Config = Config()


        self.kwargs = {}

        if self.Config.proxy_use:
            self.kwargs['proxy'] = (self.Config.proxy_url, self.Config.proxy_port, self.Config.proxy_secret)
            self.kwargs['connection'] = connection.ConnectionTcpMTProxyRandomizedIntermediate

    # @run_async
    def client_init(self):
        return
        self.client = TelegramClient(self.Config.session_name, self.Config.app_id, self.Config.api_hash, **self.kwargs)
        self.client.start()
        connected = self.client.is_connected()
        if not connected:
            self.client.connect()
        self.client.add_event_handler(callback=self._taking_success, event=events.NewMessage(chats=(self.Config.keeper), pattern=r'(?P<location_name>.+)\s+теперь\s+под\s+контролем\s+🤘(?P<gang_name>.+)!'))
        self.client.add_event_handler(callback=self._dzen_enhancement, event=events.NewMessage(chats=(self.Config.keeper), pattern=r'(?P<fraction_icon>(⚛️)|(🔪)|(⚙️)|(💣)|(🔰))(?P<nickname>.+)\s+постиг\s+(?P<dzen>\d+)-й\s+🏵Дзен\s+!'))
        self.client.add_event_handler(callback=self._boss_spawn, event=events.NewMessage(chats=(self.Config.keeper), pattern=r'(?P<boss_name>.+)\s+был\s+замечен\s+на\s+просторах\s+Пустоши\.'))
        self.client.run_until_disconnected()

    async def _taking_success(self, event):
        match = event.pattern_match
        update = self._inner_update(event)
        update.taking_success = TakingSuccess(match = match)
        self.event_manager.invoke_handler_update(update)

    async def _dzen_enhancement(self, event):
        match = event.pattern_match
        update = self._inner_update(event)
        update.dzen_enhancement = DzenEnhancement(match = match)
        self.event_manager.invoke_handler_update(update)

    async def _boss_spawn(self, event):
        match = event.pattern_match
        update = self._inner_update(event)
        update.boss_spawn = BossSpawn(match = match)
        self.event_manager.invoke_handler_update(update)

    def _inner_update(self, event):
        update = InnerUpdate()
        update.invoker = TelegramUser.get_by_user_id(utils.get_peer_id(event.message.to_id))
        update.player = update.invoker.player.get() if (update.invoker and update.invoker.player) else None
        if not event.message:
            update.date = event.date
        elif event.message.fwd_from:
            update.date = event.message.fwd_from.date
        else:
            update.date = event.message.date
        return update