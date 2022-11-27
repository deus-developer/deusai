import datetime
import json
import re

import telegram
from telegram import ParseMode
from telegram.ext import (
    Dispatcher,
    MessageHandler
)
from telegram.ext.filters import Filters

from config import settings
from core import (
    CommandFilter,
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update
)
from decorators import (
    command_handler,
    permissions
)
from decorators.permissions import (
    is_admin,
    is_lider,
    or_
)
from models import (
    Group,
    Player,
    RaidAssign,
    RaidResult,
    Settings,
    TelegramChat
)
from modules import BasicModule
from utils.functions import (
    CustomFilters,
    CustomInnerFilters,
    last_raid
)
from ww6StatBotWorld import Wasteland


class RaidResultModule(BasicModule):  # TODO: Полностью переработать
    module_name = 'raid_result'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_handler(MessageHandler(CustomFilters.greatwar & Filters.text, self._parse_raid_result))
        self.add_inner_handler(InnerHandler(CommandFilter('raid_inform'), self._comm_inform, [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))

        super().__init__(event_manager, message_manager, dispatcher)

        self._re_is_raid_result = re.compile(r'Итоги 👊Рейда:')

        self._re_raid_location = re.compile(
            r'(?P<km>\d+)км+\s+(?P<location_name>.+)+\s+🏆\++(?P<rating>\d+)\s+'
            r'--(?P<league>.+)--'
        )

        self._re_raid_goats = re.compile(r'🐐\s*(?P<goat>.+):\s+(?P<percentRaid>\d+.\d+)%')

        self._re_raid_topraiders = re.compile(r'🎖Лучшие рейдеры\s+(.*)')
        self._re_raid_nick = re.compile(r'(?P<nick>.+)\[(?P<goat>.*)]')

        self._convert_status = {
            30: 0,
            35: 3,
            40: 3,
            -4: 0,
            -5: 0,
            -10: 0,
            -100: 0,
            -3: 0,
            0: 0,
            10: 0,
            20: 0
        }

    def _parse_raid_result(self, bot: telegram.Bot, update: telegram.Update):
        message = update.channel_post or update.message
        post_id = message.message_id or message.forward_from_chat.id
        date = message.date.astimezone(settings.timezone).replace(minute=0, second=0, microsecond=0)
        if RaidResult.exist_rows(date):
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text='Этот рейд уже есть в базе'
            )

        text = message.text or ''
        match = self._re_is_raid_result.match(text)
        if not match:
            return

        locations = text.split('\n\n')

        for location in locations:
            location_data = self._re_raid_location.search(location)
            if not location_data:
                continue

            km, location_name, up_rating, league = location_data.groups()
            raid_goats = self._re_raid_goats.findall(location)
            raid_nicks = self._re_raid_topraiders.search(location)

            our_raid = []
            _goats = [_g.name for _g in Group.select(Group.name).where(Group.type == 'goat')]
            for _goat in raid_goats:
                if _goat[0] in _goats:
                    our_raid.append(_goat)

            wingoat = ('[Не захваченно]', 0.00)
            ourgoat = ('', 0.00)

            if len(raid_goats) != 0:
                wingoat = raid_goats[0]

            if len(our_raid) != 0:
                ourgoat = our_raid[0]

            top_raiders = []
            if raid_nicks:
                top_raiders = [self._re_raid_nick.search(nicksamp).groups() for nicksamp in raid_nicks.group(1).split(',')]

            raid_result = RaidResult(
                km=km,
                name=location_name,
                rating=up_rating,
                league=league,
                wingoat=wingoat[0],
                wingoatpercent=wingoat[1],
                ourgoat=ourgoat[0],
                ourgoatpercent=ourgoat[1],
                goats=json.dumps(raid_goats),
                raiders=json.dumps(top_raiders),
                post_id=post_id,
                date=date
            )
            raid_result.save()

        if date >= last_raid():
            self._auto_result()

    @permissions(is_admin)
    def _comm_inform(self, update: Update):
        return self._auto_result()

    def _auto_result(self):
        date = last_raid(datetime.datetime.now() + datetime.timedelta(seconds=10))
        locations = RaidResult \
            .select() \
            .where(RaidResult.date == date)
        status = False
        if len(locations) == 0:
            message = f'Увы, нет данных по рейду <b>{date.strftime("%d.%m.%Y %H:%M")}</b>.'
            status = True
        else:
            leagues = {}
            post_id = None
            for location in locations:
                if post_id is None:
                    post_id = location.post_id

                goats = leagues.get(location.league, {})
                info = goats.get(location.wingoat, {})

                locs_icons = info.get('locations', None)
                loc_icon = Wasteland.raid_locations_by_km.get(location.km, ('NonName', 'NonIcon'))[1]
                if locs_icons:
                    locs_icons.append(f'{loc_icon}({location.km})')
                else:
                    locs_icons = [f'{loc_icon}({location.km})']
                info.update(
                    {
                        'up_rating': info.get('up_rating', 0) + location.rating,
                        'locations': locs_icons,
                    }
                )
                goats.update(
                    {
                        location.wingoat: info
                    }
                )
                leagues.update(
                    {
                        location.league: goats
                    }
                )

            our_goats = [_g.name for _g in Group.select(Group.name).where((Group.type == 'goat') and (Group.is_active == True))]
            results = []

            leagues = sorted(leagues.items(), key=lambda pars: pars[0])

            for league, goats in leagues:
                results.append(f'\n<b>{league}</b>')
                goats = sorted(goats.items(), key=lambda pars: pars[1].get('up_rating', 0), reverse=True)
                for name, info in goats:
                    c_name = f'<b>{name}</b>' if name in our_goats else name
                    results.append(f"   🐐{c_name} +{info.get('up_rating', 0)}🍀\n     {' '.join(info.get('locations', []))}")

            message = f"<i>#Итогирейда от <a href='https://t.me/greatwar/{post_id}'>{date.strftime('%d.%m.%Y %H:%M')}</a></i>\n" + '\n'.join(results)
            status = True

        users = RaidAssign.select(Player.telegram_user_id.alias('chat_id')) \
            .join(Player, on=(Player.id == RaidAssign.player_id)) \
            .join(Settings, on=(Player.settings_id == Settings.id)) \
            .where((RaidAssign.time == date) & (Settings.pings['notify_raid_tz_report'] == 'true') & (RaidAssign.km_assigned << Wasteland.raid_kms_tz)) \
            .dicts()

        for user in users:
            try:
                self.message_manager.send_message(chat_id=user['chat_id'], text='<b>Рейд окончен! Уходи с точки!!!!</b>', parse_mode=ParseMode.HTML)
            except (Exception,):
                pass

        for chat in TelegramChat.select(TelegramChat.chat_id).where(TelegramChat.is_active == True).dicts():
            try:
                self.message_manager.send_message(chat_id=chat['chat_id'], text=message, parse_mode=ParseMode.HTML)
            except (Exception,):
                pass

    @permissions(or_(is_admin, is_lider))
    @command_handler(
        regexp=re.compile(r'(?P<group_name>.+)\s+(?P<period>\d+)', re.IGNORECASE),
        argument_miss_msg='Пришли сообщение в формате "/raid_stat Группа Период(число дней)"'
    )
    def _raids_statistics(self, update: Update, match, *args, **kwargs):
        message = update.telegram_update.message
        group_name, period = match.groups()
        group = Group.get_by_name(group_name)
        if not group:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f'Группы "{group_name}" не существует.'
            )
        period = int(match.group('period'))
        date_start = message.date.astimezone(settings.timezone).replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=period)

        pls = group.members
        result_dicts = {}
        for player in pls:
            raids = player.raids_assign
            for raid in raids.filter(RaidAssign.time >= date_start).order_by(RaidAssign.time):
                status = self._convert_status.get(raid.status_id, 1)
                if status == 3:
                    status = 4 if (raid.km_assigned in Wasteland.raid_kms_tz) else 3

                if raid.status == 20 and raid.km_assigned in Wasteland.raid_kms_tz:
                    status = 1

                gang_dict = result_dicts.get(group.name, {})
                date = raid.time.strftime('%d.%m.%Y')
                time = raid.time.strftime('%H:%M')
                day_dict = gang_dict.get(date, {})
                time_list = day_dict.get(time, None)
                if not time_list:
                    time_list = []
                time_list.append(
                    {
                        'nickname': player.nickname,
                        'status': status
                    }
                )

                day_dict.update(
                    {
                        time: time_list
                    }
                )
                gang_dict.update(
                    {
                        date: day_dict
                    }
                )
                result_dicts.update(
                    {
                        group.name: gang_dict
                    }
                )

        u = Update()
        u.chat_id = message.chat_id
        u.raid_final_result = result_dicts
        self.event_manager.invoke_handler_update(u)

    # @permissions(is_admin)
    # def _test_new_report(self, update: Update):
    #     raid_time = last_raid(datetime.datetime.now() + datetime.timedelta(seconds = 10))
    #     pins = \

# Типы ПИНов
# 👊Участвовали: Участвовали + Подтвердились
# ❌Не дошли: Отказались + Не дошли
# 😑Проигнорировали: Не принято/Не прочитано 

# Простая версия, авто репорта

# 👊Рейд 01:00:00
# ⏳Результаты: 01:00:05

# 📦05км WunderWaffe [100.0%]
# 🕳09км Δeus Σx Machina [100.0%]
#         100%👊 0%❌ 0%😑
# 💊12км FǁȺǁggǁØǁAT [80.3%]
# 🍗16км Pro100KAPIBARY [86.0%]
# 🔹20км Каганат ВХ [100.0%]
# ❤24км Δeus Σx Machina [51.2%]
#         100%👊 0%❌ 0%😑
# 💡28км New Vegas [100.0%]
# 💾32км FǁȺǁggǁØǁAT [100.0%]
# 🔩38км Каганат ВХ [100.0%]
# 🔗46км New Vegas [95.7%]
# 🗼53км Pro100KAPIBARY [59.8%]
# ⛲54км Ангирский Совет [100.0%]
# ☢57км Ангирский Совет [100.0%]
# 🏛63км Бафомет [100.0%]

# Итого: 100%👊 0%❌ 0%😑

# 👊Рейд 01:00:00
# ⏳Результаты: 01:00:05

# 📦[05км] WunderWaffe [100.0%]
# 🕳[09км] Δeus Σx Machina [100.0%]
# 💊[12км] FǁȺǁggǁØǁAT [80.3%]
# 🍗[16км] Pro100KAPIBARY [86.0%]
# 🔹[20км] Каганат ВХ [100.0%]
# ❤️[24км] Δeus Σx Machina [51.2%]
# 💡[28км] New Vegas [100.0%]
# 💾[32км] FǁȺǁggǁØǁAT [100.0%]
# 🔩[38км] Каганат ВХ [100.0%]
# 🔗[46км] New Vegas [95.7%]
# 🗼[53км] Pro100KAPIBARY [59.8%]
# ⛲️[54км] Ангирский Совет [100.0%]
# ☢️[57км] Ангирский Совет [100.0%]
# 🏛[63км] Бафомет [100.0%]


# ◼️Топ:
# ▫️Δeus Σx Machina +35🥬
# ▫️FǁȺǁggǁØǁAT +35🥬
# ▫️Pro100KAPIBARY +35🥬
# ▫️Каганат ВХ +35🥬
# ▫️New Vegas +35🥬
# ▫️Ангирский Совет +35🥬
# ▫️Бафомет +20🥬
# ▫️WunderWaffe +15🥬

# Админская версия, авто репорта

# 👊Рейд ДАТА 01:00:00
# ⏳Результаты:       01:00:05

# ✅🕳[9км] 12👊(+0📍+0👟) 100% 
# ✅❤️[24км] 7👊(+1📍+1👟) 63,2% - процент это результат рейда с канала рупора или теребоньк

# Итого — 19 из 42 (72.2%) - процент неверный, указан для примера
# Итого с 👟 — 21 из 42 (73.6%)


# def _parse_raid_result_new(self, bot: telegram.Bot, update: telegram.Update):
#     message = update.message
#     post_id = message.message_id
#     date = message.date.replace(minute=0, second=0, microsecond=0)

#     text = message.text or ''
#     match = self._re_is_raid_result.match(text)
#     if not match:
#         return

#     locations = text.split('\n\n')
#     raid_result = RaidResult.get_or_create(time=date)
#     if raid_result.locations:
#         return
#     for location in locations:
#         location_data = self._re_raid_location.search(location)
#         if not location_data:
#             continue

#         km, location_name, up_rating, league = location_data.group('km', 'location_name', 'rating', 'league')
#         km = int(km)
#         if location_name not in Wasteland.raid_locations:
#             self.message_manager.send_message(chat_id=settings.ADMIN_CHAT_ID, text=f'Новая рейдовая локация? ({location_name})')

#         raid_goats = self._re_raid_goats.finditer(location)

#         goats_results = {}
#         for goat in raid_goats:
#             name, perent = goat.group('goat', 'percentRaid')
#             group = Group.get_by_name(name, 'goat')
#             if not group:
#                 group = Group.create(name=name, group_type='goat')
#             goats_results.update({name: float(perent)})

#         raid_nicks = self._re_raid_topraiders.search(location)

#         top_raiders = []
#         if raid_nicks:
#             top_raiders = [self._re_raid_nick.search(nicksamp).groups() for nicksamp in raid_nicks.group(1).split(',')]
#         location = RaidResultLocation(raid=raid_result, km=km, )
#         print(km, location_name, up_rating, league, goats_results, top_raiders)
#         if date >= last_raid():
#             self._auto_result()
# (?P<km>\d+)км\s+(?P<name>.+)\s+🏆\+(?P<rating>\d+)
# --(?P<liga>.+)--
# (?P<goats>[\s\S]+)
# 🎖Лучшие рейдеры\s*(?P<raiders>.*)
