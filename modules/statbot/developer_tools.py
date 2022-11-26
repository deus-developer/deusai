import telegram
import os
import re
import datetime
import peewee
from collections import defaultdict
import base64
import json
from jinja2 import Template
from telegram import ChatAction
from tempfile import NamedTemporaryFile
from telegram.ext import Dispatcher
from decorators import command_handler, permissions
from decorators.permissions import is_developer
from core import EventManager, MessageManager, Handler as InnerHandler, CommandFilter, Update
from modules import BasicModule
from models import Player, TelegramUser, TelegramChat, RaidsInterval, KarmaTransition, PlayerRecivedThrough, Settings, PlayerStatHistory
from utils.functions import CustomInnerFilters
from telegram.utils.helpers import mention_html
from modules.statbot.karma import Karma
from decorators.users import get_players

def pings_default():
    return {
        'sendpin': True,
        'echo': True,
        'drop_head': True,
        'ping': True,
        'weekly_report': True,
        'notify_raid_3': True,
        'notify_raid_tz_10': True,
        'notify_raid_tz': True,
        'notify_raid_tz_report': True,
    }

class DeveloperToolsModule(BasicModule):
    
    module_name = 'dev_tools'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(CommandFilter(command='export_chats', description='Сейвит выгрузку чатов на сервере'), self._exp, custom_filters=[CustomInnerFilters.private]))
        self.add_inner_handler(InnerHandler(CommandFilter(command='duplicating_players', description='Выводит игроков с похожими никами'), self._duplicating_players, custom_filters=[CustomInnerFilters.private]))

        self.add_inner_handler(InnerHandler(CommandFilter('commands'), self._commands, custom_filters=[CustomInnerFilters.private]))
        self.add_inner_handler(InnerHandler(CommandFilter('konkurs_stat'), self._konkurs_stat, custom_filters=[]))
        self.add_inner_handler(InnerHandler(CommandFilter('raids_optimize'), self._raids_optimize, custom_filters=[CustomInnerFilters.private]))

        super().__init__(event_manager, message_manager, dispatcher)

    @permissions(is_developer)
    @command_handler(regexp=re.compile(r'(?P<start>\d{2}\.\d{2}\.\d{4}:\d{2})\s+-\s+(?P<end>\d{2}\.\d{2}\.\d{4}:\d{2})'),
                     argument_miss_msg='Пришли сообщение в формате "/konkurs 00.00.2020:09 - 01.00.2020:09 @User"')
    @get_players(include_reply=True, break_if_no_players=True)
    def _konkurs_stat(self, update: Update, match, players):
        time1, time2 = match.group('start', 'end')
        try:
            time1 = datetime.datetime.strptime(time1, '%d.%m.%Y:%H')
        except Exception as e:
            return update.telegram_update.message.reply_text(f'Время начала конкурса указано неверно!\n<code>{e}</code>', parse_mode='HTML')

        try:
            time2 = datetime.datetime.strptime(time2, '%d.%m.%Y:%H')
        except Exception as e:
            return update.telegram_update.message.reply_text(f'Время конца конкурса указано неверно!\n<code>{e}</code>', parse_mode='HTML')
        if time1 > time2:
            return update.telegram_update.message.reply_text(f'Время начала конкурса не может быть позднее конца!')
        players = [p.id for p in players]
        print(players)
        t1_date = PlayerStatHistory.alias('t1_date')
        t2_date = PlayerStatHistory.alias('t2_date')
        t3_main = PlayerStatHistory.alias('t3_main')
        dates_start = t1_date.select(t1_date.player_id, peewee.fn.MAX(t1_date.time).alias('maxdate'))\
                                       .where(t1_date.time < time1)\
                                       .group_by(t1_date.player_id).alias('dates_start')

        dates_end = t2_date.select(t2_date.player_id, peewee.fn.MAX(t2_date.time).alias('maxdate'))\
                                       .where(t2_date.time < time2)\
                                       .group_by(t2_date.player_id).alias('dates_end')

        history = t3_main.select()\
                                   .join(dates_start, on=((t3_main.player_id == dates_start.c.player_id) & (t3_main.time == dates_start.c.maxdate)))\
                                   .join(dates_end, on=((t3_main.player_id == dates_end.c.player_id) & (t3_main.time == dates_end.c.maxdate)))\
                                   .order_by(t3_main.player_id, t3_main.time)\
                                   .filter(t3_main.player_id << players)\
                                   .dicts()
        print(history)
        fields = ('time', 'hp', 'power', 'accuracy', 'oratory', 'agility')
        data = defaultdict(list)
        for stats in history:
            print(stats)
            data[stats['player']].append(stats)

        delts = defaultdict(defaultdict)
        for player_id, rages in data.items():
            for field in fields:
                delts[player_id][f'first_{field}'] = rages[0][field]
                delts[player_id][f'last_{field}'] = rages[-1][field]
                delts[player_id][f'delta_{field}'] = rages[-1][field] - rages[0][field]
        forrmater_report = (
                f'Анализ событий в период с {time1} по {time2}\n'
                f'Участников: {len(delts.keys())}\n\n'
            )
        for player_id, values in delts.items():
            player = Player.get_or_none(id=player_id)
            if not player:
                continue
            forrmater_report += (
                    f'<b>PlayerID: {mention_html(player.telegram_user_id, player.nickname)}</b>\n'
                    f'<code>Время первого пип боя: {values["first_time"]}\n'
                    f'Время второго пип боя: {values["last_time"]}\n'
                    f'ХП {values["first_hp"]} -> {values["last_hp"]} [{values["delta_hp"]}]\n'
                    f'Сила {values["first_power"]} -> {values["last_power"]} [{values["delta_power"]}]\n'
                    f'Меткость {values["first_accuracy"]} -> {values["last_accuracy"]} [{values["delta_accuracy"]}]\n'
                    f'Харизма {values["first_oratory"]} -> {values["last_oratory"]} [{values["delta_oratory"]}]\n'
                    f'Ловкость {values["first_agility"]} -> {values["last_agility"]} [{values["delta_agility"]}]</code>\n'
                    f'Суммарно: {values["delta_hp"] + values["delta_power"] + values["delta_accuracy"] + values["delta_oratory"] + values["delta_agility"]}\n\n'
                )
        return update.telegram_update.message.reply_text(forrmater_report, parse_mode='HTML')

    @permissions(is_developer)
    def _settings_setup(self, update: Update):
        Settings.update(pings=pings_default()).execute()
        update.telegram_update.message.reply_text('Готово!')

    @permissions(is_developer)
    def _raids_optimize(self, update: Update):
        now = datetime.datetime.now()
        interval = RaidsInterval.interval_by_date(now, offset=0)
        
        players_ids = [x.id for x in Player.select().where(Player.is_active == True)]

        players_q = KarmaTransition.select(
                                            peewee.fn.SUM(KarmaTransition.amount).alias('total'),
                                            PlayerRecivedThrough.player_id.alias('player_id'),
                                            )\
                                    .join(PlayerRecivedThrough, on=(PlayerRecivedThrough.transition_id == KarmaTransition.id))\
                                    .where(
                                            (PlayerRecivedThrough.player_id << players_ids) & \
                                            (KarmaTransition.created_date.between('2020-09-12 20:48:10', '2020-09-12 20:48:19')) & \
                                            (KarmaTransition.module_name == 'raid_rewards') & \
                                            (KarmaTransition.description == 'Обработка недели рейдов.'))\
                                    .group_by(PlayerRecivedThrough.player_id)\
                                    .dicts()
        interval_text = f'с {interval.start_date.strftime("%d.%m %H-%M")} по {interval.last_date.strftime("%d.%m %H-%M")}'

        for player in players_q:
            pl = Player.get_or_none(id=player['player_id'])
            if not pl:
                print(f'{player["player_id"]} error (:')
                continue

            u = Update()
            u.karma_ = Karma(module_name='raids_optimize', recivier=pl, sender=pl, amount=-player['total'], description=f'Аннулирование наград за рейды')
            self.event_manager.invoke_handler_update(u)
            self.message_manager.send_message(chat_id=pl.telegram_user_id, text='Я аннулировал все зачисления/списания кармы по рейдам.\n'
                                                                                f'За период {interval_text}.\n'
                                                                                f'Прибавил тебе = {-player["total"]}☯️')

    @permissions(is_developer)
    def _commands(self, update: Update): #TODO: Добавить вывод описания всех обработчиков
        output = f'Всего обработчиков в боте: {len(self.event_manager.handlers)}\n'
        output += 'Те что являются командами ниже:\n'
        for handler in self.event_manager.handlers:
            if isinstance(handler.filter, CommandFilter):
                output += f'▫️ /{handler.filter.command}'
                if handler.filter.description:
                    output += f'\t▫️{handler.filter.description}'
                output += '\n'

        update.telegram_update.message.reply_text(text=output)

    @permissions(is_developer)
    def _duplicating_players(self, update: Update):
        message = update.telegram_update.message
        remaster = []
        for player in Player.select():
            duplings = Player.select().where(peewee.fn.LOWER(Player.nickname).contains(player.nickname))
            if duplings.count() == 1:
                continue
            duplings_ = []
            for x in duplings:
                if x.nickname != player.nickname:
                    duplings_.append(f'\t\t\t{x.nickname}')

            duplings_ = '\n'.join(duplings_)
            remaster.append(f'{player.nickname}:\n{duplings_}')
        if not remaster:
            remaster = ['Упс, нет таких']
        self.message_manager.send_split(chat_id = message.chat_id, msg='\n'.join(remaster), n=50)

    @permissions(is_developer)
    def _exp(self, update: Update):
        default = datetime.datetime.now() - datetime.timedelta(days=2)
        try:
            date = datetime.datetime.strptime(update.command.argument, '%Y.%m.%d') if update.command.argument else default
        except Exception as e:
            date = default

        self._export_chats(date=date)
        self.message_manager.send_message(chat_id=update.invoker.chat_id, text='Сохранил на сервере. ./index.html')

    def _export_chats(self, date=None): #TODO: Провести переработку. Создать полноценный онлайн клиент для бота на основе VUE.js / Electron?
        date = date or datetime.datetime.now() - datetime.timedelta(days=2)

        template = Template(open('files/templates/mainchat_template.html', 'r', encoding='utf-8').read())
        contact_template = Template(open('files/templates/chat_template.html', 'r', encoding='utf-8').read())
        dialog_template = Template(open('files/templates/dialog_template.html', 'r', encoding='utf-8').read())
        message_template = Template(open('files/templates/message_template.html', 'r', encoding='utf-8').read())
        names = {}

        for chat in TelegramChat.select():
            names.update({str(chat.chat_id): chat.title})
        for user in TelegramUser.select():
            names.update({str(user.chat_id): f'@{user.username}'})

        chats = []
        for dialog in sorted(os.listdir('files/dialogs')):
            avatar_path = f'files/images/{dialog}_avatar.jpg'
            if not os.path.exists(avatar_path):
                avatar_path = 'files/images/default_avatar.default.jpg'
            name = names.get(dialog, f'Диалог {dialog}')
            messages = []
            for update_file in sorted(os.listdir(f'files/dialogs/{dialog}/'), key=self.regex_updatesort):
                try:
                    update = json.load(open(f'files/dialogs/{dialog}/{update_file}', 'r', encoding='utf-8'))
                except Exception as e:
                    continue
                user_data = update.get('_effective_user', None)
                chat_data = update.get('_effective_chat', None)
                message_data = update.get('_effective_message', None)
                if not message_data:
                    continue
                d = self.timestamp(message_data.get('date', 0))
                if d < date:
                    continue
                message_data.update({'date': d})
                message_data.update({'forward_date': self.timestamp(message_data.get('forward_date', 0))})
                forward = message_data.get('forward_from', None)

                message_data.update({'text': message_data.get('text', '').replace('\n', '<br>')})
                photo = None
                messages.append(message_template.render(user=user_data, message=message_data, forward=forward, photo=photo))

            chats.append(
                    {
                        'chatid': dialog,
                        'name': name,
                        'avatar_path': self.image(avatar_path),
                        'messages': '\n'.join(messages),
                        'messages_count': len(messages)
                    }
                )

        html = template.render(contacts=[contact_template.render(**x) for x in chats], dialogs = [dialog_template.render(**x) for x in chats])
        open('index.html', 'w', encoding='utf-8').write(html)

    def regex_updatesort(self, x):
        return int(x.split('.')[0])

    def image_to_base64(self, path=None):
        if not path:
            return None
        return 'data:image/jpeg;charset=utf-8;base64, ' + base64.b64encode(open(path, "rb").read()).decode()

    def image(self, path=None, base64=True):
        return None # Minimum size
        if not path:
            return None
        return path if not base64 else self.image_to_base64(path)

    def timestamp(self, unix=0):
        return datetime.datetime.fromtimestamp(unix)