import datetime
import json
import re
from typing import Match

import telegram
from telegram.ext import Dispatcher, MessageHandler
from telegram.ext.filters import Filters

from core import EventManager, MessageManager, InnerHandler, CommandFilter, InnerUpdate
from decorators import permissions, command_handler
from decorators.permissions import is_admin, is_lider, or_
from models import RaidResult, Group, TelegramChat, RaidAssign, Settings, Player
from modules import BasicModule
from utils.functions import CustomFilters, CustomInnerFilters, get_last_raid_date
from wasteland_wars import constants


class RaidResultModule(BasicModule):
    module_name = 'raid_result'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_handler(MessageHandler(CustomFilters.greatwar & Filters.text, self._parse_raid_result))
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('raid_inform'),
                self._comm_inform,
                [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

        self._re_is_raid_result = re.compile(r'Итоги 👊Рейда:')

        self._re_raid_location = re.compile(
            r'(?P<km>\d+)км+\s+(?P<location_name>.+)+\s+🏆\++(?P<rating>\d+)[\s]+'
            r'--(?P<league>.+)--'
        )

        self._re_raid_goats = re.compile(r'🐐\s*(?P<goat>.+):\s+(?P<percentRaid>\d+.\d+)%')

        self._re_raid_topraiders = re.compile(r'🎖Лучшие рейдеры\s+(.*)')
        self._re_raid_nick = re.compile(r'(?P<nick>.+)\[(?P<goat>.*)\]')

        self._convert_status = {30: 0, 35: 3, 40: 3, -4: 0, -5: 0, -10: 0, -100: 0, -3: 0, 0: 0, 10: 0, 20: 0}

    def _parse_raid_result(self, _: telegram.Bot, update: telegram.Update):
        message = update.channel_post or update.message
        post_id = message.message_id or message.forward_from_chat.id
        date = message.date.replace(minute=0, second=0, microsecond=0)
        if RaidResult.exist_rows(date):
            return

        match = self._re_is_raid_result.match(message.text)
        if not match:
            return

        locations = message.text.split('\n\n')

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
                top_raiders = [self._re_raid_nick.search(nicksamp).groups() for nicksamp in
                               raid_nicks.group(1).split(',')]

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

        if date >= get_last_raid_date():
            self._auto_result()

    @permissions(is_admin)
    def _comm_inform(self, _: InnerUpdate):
        return self._auto_result()

    def _auto_result(self):
        date = get_last_raid_date(datetime.datetime.now() + datetime.timedelta(seconds=10))
        locations = RaidResult \
            .select() \
            .where(RaidResult.date == date)

        status = False
        if len(locations) == 0:
            text = f'Увы, нет данных по рейду <b>{date.strftime("%d.%m.%Y %H:%M")}</b>.'
            status = True

        leagues = {}

        if not status:
            post_id = None
            for location in locations:
                if post_id is None:
                    post_id = location.post_id

                goats = leagues.get(location.league, {})
                info = goats.get(location.wingoat, {})

                locs_icons = info.get('locations', None)
                loc_icon = constants.raid_locations_by_km.get(location.km, ('NonName', 'NonIcon'))[1]
                if locs_icons:
                    locs_icons.append(f'{loc_icon}({location.km})')
                else:
                    locs_icons = [f'{loc_icon}({location.km})']
                info.update({
                    'up_rating': info.get('up_rating', 0) + location.rating,
                    'locations': locs_icons,
                })
                goats.update({location.wingoat: info})
                leagues.update({location.league: goats})

            our_goats = [_g.name for _g in
                         Group.select(Group.name).where((Group.type == 'goat') and (Group.is_active == True))]
            results = []

            leagues = sorted(leagues.items(), key=lambda pars: pars[0])

            for league, goats in leagues:
                results.append(f'\n<b>{league}</b>')
                goats = sorted(goats.items(), key=lambda pars: pars[1].get('up_rating', 0), reverse=True)
                for name, info in goats:
                    c_name = f'<b>{name}</b>' if name in our_goats else name
                    results.append(
                        f"   🐐{c_name} +{info.get('up_rating', 0)}🍀\n     {' '.join(info.get('locations', []))}")

            text = f"<i>#Итогирейда от <a href='https://t.me/greatwar/{post_id}'>{date.strftime('%d.%m.%Y %H:%M')}</a></i>\n" + '\n'.join(
                results)

        users = RaidAssign.select(Player.telegram_user_id.alias('chat_id')) \
            .join(Player, on=(Player.id == RaidAssign.player_id)) \
            .join(Settings, on=(Player.settings_id == Settings.id)) \
            .where((RaidAssign.time == date) & (Settings.pings['notify_raid_tz_report'] == 'true') & (
                RaidAssign.km_assigned << constants.raid_kms_tz)) \
            .dicts()

        for user in users:
            self.message_manager.send_message(
                chat_id=user['chat_id'],
                text='<b>Рейд окончен! Уходи с точки!!!!</b>'
            )

        for chat in TelegramChat.select(TelegramChat.chat_id).where(TelegramChat.is_active == True).dicts():
            self.message_manager.send_message(
                chat_id=chat['chat_id'],
                text=text
            )

    @permissions(or_(is_admin, is_lider))
    @command_handler(
        regexp=re.compile(r'(?P<group_name>.+)\s+(?P<period>\d+)', re.IGNORECASE),
        argument_miss_msg='Пришли сообщение в формате "/raid_stat Группа Период(число дней)"'
    )
    def _raids_statistics(self, update: InnerUpdate, match: Match):
        message = update.telegram_update.message
        group_name, period = match.groups()
        group = Group.get_by_name(group_name)
        if not group:
            return self.message_manager.send_message(
                chat_id=message.chat_id,
                text=f'Группы "{group_name}" не существует.'
            )

        period = int(match.group('period'))
        date_start = message.date.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=period)

        pls = group.members
        result_dicts = {}
        for player in pls:
            raids = player.raids_assign
            for raid in raids.filter(RaidAssign.time >= date_start).order_by(RaidAssign.time):
                status = self._convert_status.get(raid.status_id, 1)
                if status == 3:
                    status = 4 if (raid.km_assigned in constants.raid_kms_tz) else 3

                if raid.status == 20 and raid.km_assigned in constants.raid_kms_tz:
                    status = 1

                gang_dict = result_dicts.get(group.name, {})
                date = raid.time.strftime('%d.%m.%Y')
                time = raid.time.strftime('%H:%M')
                day_dict = gang_dict.get(date, {})
                time_list = day_dict.get(time)

                if not time_list:
                    time_list = []

                time_list.append({
                    'nickname': player.nickname,
                    'status': status
                })

                day_dict.update({time: time_list})
                gang_dict.update({date: day_dict})
                result_dicts.update({group.name: gang_dict})

        u = InnerUpdate()
        u.chat_id = message.chat_id
        u.raid_final_result = result_dicts
        self.event_manager.invoke_handler_update(u)
