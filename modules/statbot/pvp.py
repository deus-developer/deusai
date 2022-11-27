import datetime
import re
import time
from typing import List

import peewee
from pytils import dt
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    CallbackQueryHandler,
    Dispatcher
)
from telegram.utils.helpers import mention_html

from core import (
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update,
    UpdateFilter
)
from decorators.update import inner_update
from decorators.users import get_player
from models import (
    Group,
    InventoryItem,
    Item,
    PVP,
    Player,
    Radar,
    TelegramUser
)
from modules import BasicModule
from modules.statbot.parser import PlayerParseResult
from utils.functions import (
    CustomInnerFilters,
    sha1
)


def median(array):
    len_l = len(array)
    array = sorted(array)
    div, mod = divmod(len_l, 2)
    if mod == 0 and len_l > 0:
        return (array[div - 1] + array[div]) / 2.0
    elif mod == 1:
        return array[div]


def searchclose(array: list[int], number: int) -> int:
    return min(array, key=lambda a: abs(a - number))


class PVPPlayer:
    nickname: str
    max_hp: int
    max_damage: int
    min_damage: int
    median_damage: int
    attacks: List[int]

    regeneration: int
    BATCOH: int

    def __init__(self):
        self.nickname = ''
        self.max_hp = self.max_damage = self.min_damage = self.median_damage = 0
        self.regeneration = self.BATCOH = 0
        self.attacks = []

    def __str__(self):
        return (
            f'NICKNAME: {self.nickname}\n'
            f'MAX HP: {self.max_hp}\n'
            f'MAX DAMAGE: {self.max_damage}\n'
            f'MEDIAN DAMAGE: {self.median_damage}\n'
            f'MIN DAMAGE: {self.min_damage}\n'
            f'REGENERATION {self.regeneration}\n'
            f'BATCOH {self.BATCOH}\n'
            f'ATTACKS {"; ".join([str(x) for x in sorted(self.attacks)])}'
        )


class PlayerInfo:
    nickname: str

    goat: str
    gang: str

    hp: int
    attack: int
    dzen: int

    regeneration_l: int
    BATCOH_l: int

    code: str
    time: datetime.datetime

    def __init__(self):
        self.nickname = '[-- Nickname --]'
        self.goat = '[-- Goat --]'
        self.gang = '[-- Gang --]'

        self.hp = self.attack = self.dzen = self.regeneration_l = self.BATCOH_l = 0
        self.code = '[-- CODE --]'
        self.time = datetime.datetime.now()


class PVPModule(BasicModule):  # TODO: Полностью переработать
    """
    message sending
    """
    module_name = 'pvp'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(UpdateFilter('pvp'), self._pvp_handler, [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(UpdateFilter('sum_stat_top'), self._wwtop_handler, [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(UpdateFilter('meeting'), self._meeting_show_order, [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(UpdateFilter('dome'), self._dome_handler, [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(UpdateFilter('getto'), self._getto_handler, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(
            InnerHandler(UpdateFilter('pokemob_dead'), self._pokemob_dead_handler, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private])
        )
        self.add_inner_handler(InnerHandler(UpdateFilter('scuffle'), self._scuffle_handler, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(UpdateFilter('lynch'), self._lynch_handler, [CustomInnerFilters.from_player, CustomInnerFilters.from_admin_chat_or_private]))
        self.add_inner_handler(InnerHandler(UpdateFilter('view'), self._view_handler_update, [CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]))
        self.add_inner_handler(InnerHandler(UpdateFilter('dzen_enhancement'), self._dzen_handler, []))

        self._regen_levels = [0, 10, 20, 30, 50]
        self._BATCOH_levels = [0, 20, 40, 60, 80]

        self._regen_agility = [0, 100, 250, 500, 1150]
        self._BATCOH_accuracy = [0, 100, 250, 500, 1150]

        self._re_pvp_profile = re.compile(r'^pvp_profile_(?P<player_id>\d+)$')
        self.add_handler(CallbackQueryHandler(self._pvp_profile_inline, pattern=self._re_pvp_profile))

        self._order_meeting_show = []
        super().__init__(event_manager, message_manager, dispatcher)

        self.event_manager.scheduler.add_job(self._meeting_show_job, 'interval', seconds=1)

    def _pokemob_dead_handler(self, update: Update):
        pokemob_dead = update.pokemob_dead
        player = Player.get_or_none(nickname=pokemob_dead.nickname)
        if not player:
            main_text = 'Не знаю кто это, но если ты в ТЗ, то беги'
        else:
            main_text = self._generate_text_profile(player)
        self.message_manager.send_message(chat_id=update.invoker.chat_id, text=main_text, parse_mode='HTML')

    def _lynch_handler(self, update: Update):
        main_text = None
        buttons = []
        players = Player.select().where(
            (Player.nickname << [x.nickname for x in update.lynch]) &
            ((Player.hp != 0) | (Player.attack != 0) | (Player.dzen != 0)) &
            (Player.is_active == False)
        )
        for idx, player in enumerate(players, 1):
            if main_text is None:
                main_text = self._generate_text_profile(player)
            buttons.append([InlineKeyboardButton(text=f'[{idx}] {player.nickname}', callback_data=f'pvp_profile_{player.id}')])

        if main_text is None:
            main_text = 'Никого из них не знаю'

        markup = InlineKeyboardMarkup(buttons) if len(buttons) > 1 else None
        self.message_manager.send_message(chat_id=update.invoker.chat_id, text=main_text, parse_mode='HTML', reply_markup=markup)

    def _scuffle_handler(self, update: Update):
        scuffle = update.scuffle
        player = Player.get_or_none(nickname=scuffle.winner)
        if not player:
            main_text = 'Не знаю кто это, но если ты в ТЗ, то беги'
        else:
            main_text = self._generate_text_profile(player)
        self.message_manager.send_message(chat_id=update.invoker.chat_id, text=main_text, parse_mode='HTML')

    def _dzen_handler(self, update: Update):
        player, created = Player.get_or_create(nickname=update.dzen_enhancement.nickname)
        if created or player.last_update < update.date:
            player.fraction = update.dzen_enhancement.fraction
            player.save()
            player.add_stats(
                karma=player.karma,
                hp=player.hp,
                attack=player.attack,
                defence=player.defence,
                power=player.power,
                accuracy=player.accuracy,
                oratory=player.oratory,
                agility=player.agility,
                stamina=player.stamina,
                raids21=player.raids21, raid_points=player.raid_points, loose_raids=player.loose_raids, loose_weeks=player.loose_weeks,
                dzen=player.dzen if player.dzen > update.dzen_enhancement.dzen else update.dzen_enhancement.dzen,
                sum_stat=player.sum_stat,
                time=update.date,
                regeneration_l=player.regeneration_l, batcoh_l=player.batcoh_l
            )

    def _view_handler_update(self, update: PlayerParseResult):
        message = update.telegram_update.message
        view = update.view

        nicknames = [x.nickname for x in view.players]
        isset_players = []
        radars_update = []
        insert_codes = [
            {
                Player.nickname: x.nickname,
                Player.pu_code: x.u_command,
                Player.last_update: update.date
            } for x in view.players
        ]

        for player in Player.select(Player.id, Player.nickname).where(Player.nickname << nicknames).dicts():
            radars_update.append(
                {
                    'player_id': player['id'],
                    'km': view.km,
                    'status': 0,
                    'time': update.date
                }
            )
            isset_players.append(player['nickname'])

        player_insert = [
            {
                Player.nickname: x,
                Player.last_update: update.date
            } for x in list(set(nicknames) - set(isset_players))
        ]
        players_ids = Player.insert(player_insert).execute() if player_insert else []
        for player_id in players_ids:
            player_id = player_id[0]
            radars_update.append(
                {
                    'player_id': player_id,
                    'km': view.km,
                    'status': 0,
                    'time': update.date
                }
            )

        radars_ids = Radar.insert(radars_update).on_conflict_ignore(True).execute() if radars_update else []
        players_update = Player.insert(insert_codes).on_conflict(
            conflict_target=[Player.nickname],
            update={
                Player.pu_code: peewee.EXCLUDED.pu_code,
                Player.last_update: peewee.EXCLUDED.last_update
            },
            where=((Player.pu_code != peewee.EXCLUDED.pu_code) & (Player.last_update < peewee.EXCLUDED.last_update))
        ).execute() if insert_codes else []

        message.reply_text('Спасибо! Всех запомнил.')

    def _view_show(self, update: PlayerParseResult):
        pass

    def _meeting_show_order(self, update: PlayerParseResult):
        self._order_meeting_show.append(update)

    def _meeting_show_job(self):
        if not self._order_meeting_show:
            return
        self._meeting_show(self._order_meeting_show.pop(0))

    def _generate_text_profile(self, player: Player) -> str:
        if player.is_active:
            return f'<b>{player.nickname}</b> - Наш игрок, нападёшь на него, получишь по жёппке'
        if not (player.dzen or player.hp or player.attack):
            return f'По игроку <b>{player.nickname}</b> мало данных'

        goat, gang = player.goat, player.gang
        stats = player.stats

        regeneration = player.regeneration_l
        regeneration_percent = self._regen_levels[player.regeneration_l if 0 <= player.regeneration_l <= 4 else 4]

        batcoh_attack = int((self._BATCOH_levels[player.batcoh_l] + 100) / 100 * player.attack)
        batcoh_percent = self._BATCOH_levels[player.batcoh_l if 0 <= player.batcoh_l <= 4 else 4]

        perks_count = player.regeneration_l + player.batcoh_l

        output = [
            f'👱‍♂️ <b>{player.nickname}</b>',
            f'🐐Козел: <b>{goat.name}</b>' if goat else None,
            f'🤘Банда: <b>{gang.name}</b>' if gang else None,
            '',
            f'🛡Броня: <code>{player.defence}</code>' if player.defence != 0 else None,
            f'⚔️Урон: <code>{player.attack}</code>' if player.attack != 0 else None,
            f'❤️Здоровье: <code>{player.hp}</code>' if player.hp != 0 else None,
            f'💪Сила: <code>{player.power}</code>' if player.power != 0 else None,
            f'🎯Меткость: <code>{player.accuracy}</code>' if player.accuracy != 0 else None,
            f'🗣Харизма: <code>{player.oratory}</code>' if player.oratory != 0 else None,
            f'🤸🏽Ловкость: <code>{player.agility}</code>' if player.agility != 0 else None,
            f'🔋Выносливость: <code>{player.stamina}</code>' if player.stamina != 0 else None,
            '',
            f'🏵Дзен: <code>{player.dzen}</code>',
            '',
            f'Прокаченные перки: {perks_count} шт.' if perks_count > 0 else None,
            f'\t\t❣️Регенерация: <code>{player.regeneration_l}</code> уровень ( +{regeneration_percent}% )' if player.regeneration_l > 0 else None,
            f'\t\t⚡️Критический урон: <code>{batcoh_attack}</code> ( +{batcoh_percent}% )' if player.batcoh_l > 0 else None,
            '',
            f'<b>📅Обновлён {dt.distance_of_time_in_words(stats.time if stats else player.last_update, to_time=time.time())}</b>'
        ]
        return '\n'.join(list(filter(lambda x: x is not None, output)))

    def _meeting_show(self, update: PlayerParseResult):
        meeting = update.meeting
        message = update.telegram_update.message
        if not meeting.nic:
            return

        players = Player.select() \
            .where(peewee.fn.LOWER(Player.nickname).contains(meeting.nic.lower()) | (Player.pu_code == meeting.code)) \
            .order_by(Player.pu_code.desc()).limit(3 if meeting.type == 3 else 1)

        if not players.exists():
            return message.reply_text(text='<b>Сорян, но у меня нет информации про него.</b>', parse_mode='HTML')

        buttons = []
        main_text = None
        one_great = False
        for idx, player in enumerate(players, 1):
            pu_code = player.pu_code == meeting.code
            updates = []
            if pu_code:
                one_great = True
                goat, gang = player.goat, player.gang
                if meeting.goat != (goat.name if goat else None) and meeting.type == 3:
                    player.goat = (Group.get_by_name(meeting.goat, 'goat') or Group.create(name=meeting.goat, type='goat')) if meeting.goat else None
                    updates.append('+ Обновил 🐐Козёл игрока')
                if meeting.gang != (gang.name if gang else None) and meeting.type in [2, 3]:
                    player.gang = (Group.get_by_name(meeting.gang, 'gang') or Group.create(name=meeting.gang, type='gang')) if meeting.gang else None
                    updates.append('+ Обновил 🤘Банду игрока')

            if main_text is None:
                main_text = self._generate_text_profile(player)
            buttons.append([InlineKeyboardButton(text=f'[{idx}] {player.nickname}', callback_data=f'pvp_profile_{player.id}')])
            if updates:
                message.reply_text(text='\n'.join(updates), parse_mode='HTML')

        if not one_great:
            message.reply_text('Отправь мне пожалуйста /view, а также заново этот аватар, пожалуйста.')
        if main_text is None:
            main_text = 'Ух ля, никого не нашёл('
        markup = InlineKeyboardMarkup(buttons) if len(buttons) > 1 else None
        self.message_manager.send_message(chat_id=update.invoker.chat_id, text=main_text, parse_mode='HTML', reply_markup=markup)

    @inner_update()
    @get_player
    def _pvp_profile_inline(self, update: Update):
        player_id = int(self._re_pvp_profile.search(update.telegram_update.callback_query.data).group('player_id'))
        player = Player.get_or_none(id=player_id)
        if not player:
            return update.telegram_update.callback_query.answer('Ну ну ну, нет такого чувака!')

        text = self._generate_text_profile(player)
        if text == update.telegram_update.callback_query.message.text:
            return update.telegram_update.callback_query.answer('Ну лол ты тоже самое хочешь просмотреть :)')

        update.telegram_update.callback_query.edit_message_text(text=text, parse_mode='HTML', reply_markup=update.telegram_update.callback_query.message.reply_markup)
        update.telegram_update.callback_query.answer('Исполнил!')

    def _g_delta_icon(self, delta_time):
        if delta_time > datetime.timedelta(days=28):
            delta = 'Более 28 дней'
        elif delta_time > datetime.timedelta(days=21):
            delta = 'Более 21 дня'
        elif delta_time > datetime.timedelta(days=14):
            delta = 'Более 14 дней'
        elif delta_time > datetime.timedelta(days=7):
            delta = 'Более 7 дней'
        elif delta_time > datetime.timedelta(days=3):
            delta = ' Более 3 дней'
        else:
            delta = 'Менее трёх дней'
        return f'<code>{delta}</code>'

    def _pvp_handler(self, update: PlayerParseResult):
        message = update.telegram_update.message
        hash_ = sha1(message.text_html)

        if PVP.get_or_none(hash=hash_):
            return message.reply_text('Это ПВП уже есть в базе :)')

        pvp = update.pvp
        nics = [pvp.winner, pvp.looser]
        pls = [PVPPlayer(), PVPPlayer()]

        winner, created_winner = Player.get_or_create(nickname=pvp.winner)
        looser, created_looser = Player.get_or_create(nickname=pvp.looser)

        for idx, line in enumerate(pvp.pvp_lines):
            pl_idx = nics.index(line.player) if line.player in nics else None
            if not pls:
                continue

            pl = pls[pl_idx]
            pl.nickname = line.player
            pl.max_hp = line.health if line.health and line.health > pl.max_hp else pl.max_hp
            if line.damage:
                pl.attacks.append(int(line.damage))
            if line.regeneration:
                pl.regeneration = self._regen_levels.index(searchclose(self._regen_levels, int(line.regeneration / line.damage * 100)))
        for pl in pls:
            pl.max_damage = max(pl.attacks) if pl.attacks else 1
            pl.min_damage = min(pl.attacks) if pl.attacks else 1
            pl.median_damage = int(median(pl.attacks)) if pl.attacks else 1
            pl.BATCOH = self._BATCOH_levels.index(searchclose(self._BATCOH_levels, int(pl.max_damage / pl.median_damage * 100 - 100)))

            if not pl.nickname:
                continue
            player = winner if pl.nickname == pvp.winner else looser
            created = created_winner if pl.nickname == pvp.winner else created_looser

            if created or player.last_update < update.date:
                player.last_update = update.date

            if player.is_active:
                continue
            pl.regeneration = pl.regeneration if pl.regeneration > player.regeneration_l else player.regeneration_l
            pl.BATCOH = pl.BATCOH if pl.BATCOH > player.batcoh_l else player.batcoh_l
            batcoh_accuracy = self._BATCOH_accuracy[pl.BATCOH]
            regen_agility = self._regen_agility[pl.regeneration]

            pl.max_hp = pl.max_hp if pl.max_hp > player.hp else player.hp

            dzen = (int(pl.max_hp / 1.2) - 1550) // 50
            dzen = dzen + 1 if dzen >= 0 else 0

            player.save()
            if player.nickname == pvp.winner and update.info_line:
                radar = player.radars.order_by(Radar.time.desc()).limit(1)
                if radar:
                    radar = radar.get()
                    if radar.time < update.date:
                        Radar.create(player=player, time=update.date, km=update.info_line.distance, status=0)

            player.add_stats(
                karma=player.karma,
                hp=pl.max_hp if pl.max_hp > player.hp else player.hp,
                attack=pl.median_damage if pl.median_damage > player.attack else player.attack,
                defence=player.defence,
                power=player.power,
                accuracy=batcoh_accuracy if batcoh_accuracy > player.accuracy else player.accuracy,
                oratory=player.oratory,
                agility=regen_agility if regen_agility > player.agility else player.agility,
                stamina=player.stamina,
                dzen=dzen if dzen > player.dzen else player.dzen,
                raids21=player.raids21, raid_points=player.raid_points, loose_raids=player.loose_raids, loose_weeks=player.loose_weeks,
                regeneration_l=pl.regeneration, batcoh_l=pl.BATCOH
            )
            if not created and player.last_update > update.date:
                continue

        if (winner and looser) and winner.is_active and looser.is_active == False:
            name = f'👨🏿‍🦰Голова {looser.nickname}'
            item, created = Item.get_or_create(name=name, type='PEOPLE')
            in_inventory, created = InventoryItem.get_by_item(item=item, player=winner)
            in_inventory.amount += 1
            in_inventory.last_update = update.date if created or update.date > in_inventory.last_update else in_inventory.last_update
            in_inventory.save()
            if winner.settings.pings['drop_head']:
                self.message_manager.send_message(
                    chat_id=winner.telegram_user_id,
                    text=f'Получено "<b>{name}</b>" за пвп от <code>{update.date}</code>',
                    parse_mode='HTML'
                )
        PVP.create(
            hash=hash_,
            winner=winner,
            looser=looser,
            text=message.text_html,
            time=update.date,
            km=update.info_line.distance if update.info_line else None,
            caps=update.loot.get('🕳', None) if update.loot else None,
            mats=update.loot.get('📦', None) if update.loot else None,
        )

        if update.player.nickname == pvp.winner:
            self.message_manager.send_message(chat_id=message.chat_id, text='ГрАц!', reply_to_message_id=message.message_id)
        elif update.player.nickname == pvp.looser:
            self.message_manager.send_message(chat_id=message.chat_id, text='Пресс /F', reply_to_message_id=message.message_id)
        else:
            self.message_manager.send_message(chat_id=message.chat_id, text='Сяб за информейшн, щпоня', reply_to_message_id=message.message_id)

    def _wwtop_handler(self, update: PlayerParseResult):
        message = update.telegram_update.message
        top = update.sum_stat_top
        for pl in top.players:
            if not pl.nickname:
                continue
            player, created = Player.get_or_create(nickname=pl.nickname)
            if created or player.last_update < update.date:
                player.fraction = pl.fraction or ''
                player.last_update = update.date
                player.save()

            stats = player.stats
            if stats and stats.time > update.date:
                continue

            if stats and stats.sum_stat > pl.sum_stat:
                continue

            stats = player.add_stats(
                karma=player.karma,
                hp=player.hp,
                attack=player.attack,
                defence=player.defence,
                power=player.power,
                accuracy=player.accuracy,
                oratory=player.oratory,
                agility=player.agility,
                stamina=player.stamina,
                dzen=player.dzen,
                raids21=player.raids21, raid_points=player.raid_points, loose_raids=player.loose_raids, loose_weeks=player.loose_weeks,
                sum_stat=pl.sum_stat,
                time=update.date,
                regeneration_l=player.regeneration_l, batcoh_l=player.batcoh_l
            )

        self.message_manager.send_message(
            chat_id=message.chat_id,
            reply_to_message_id=message.message_id,
            text='Спасибо, запомнил всех!'
        )

    def _getto_handler(self, update: PlayerParseResult):
        message = update.telegram_update.message
        getto = update.getto
        v = update.player.liders.count() == 0
        for meeting in getto:
            nickname, fraction, tg_id = meeting.nickname, meeting.fraction, meeting.telegram_id
            tg_user, created = TelegramUser.get_or_create(user_id=tg_id, chat_id=tg_id)

            player = Player.get_or_none(telegram_user_id=tg_id)
            if player and player.last_update < update.date:
                if player.nickname != nickname:
                    message.reply_text(f'Игрок {nickname} раньше играл под ником {player.nickname}, пасиба, что сообщил)')
                player.nickname = nickname
                created = False
            else:
                player, created = Player.get_or_create(nickname=nickname)

            if created or player.last_update < update.date:
                player.fraction = fraction
                player.last_update = update.date
                player.gang = None
                player.goat = None

                if player.telegram_user_id is not None and player.telegram_user_id != tg_id:
                    message.reply_text(f'В базе есть игрок {player.nickname}, но у него другой tgid => кто-то меняется никами')

                player.telegram_user = tg_user
            player.save()
            if v:
                continue

            delta = self._g_delta_icon(datetime.datetime.now() - player.last_update)
            batcoh_attack = (self._BATCOH_levels[player.batcoh_l] + 100) / 100 * player.attack
            text = f'👤{mention_html(player.telegram_user_id, player.nickname)}\n'

            if player.hp:
                text += f'❤️{player.hp}'
            if player.attack:
                text += f' ⚔️~{player.attack}'
            if player.hp or player.attack:
                text += '\n'

            if player.regeneration_l:
                text += f'❣️{player.regeneration_l} Ур.'
            if player.batcoh_l:
                text += f' ⚡️{int(batcoh_attack)}'
            if player.regeneration_l or player.batcoh_l:
                text += '\n'
            text += f'Свежесть:{delta}\n'

            self.message_manager.send_message(
                chat_id=message.chat_id, text=text, reply_to_message_id=message.message_id,
                parse_mode='HTML'
            )

    def _dome_handler(self, update: PlayerParseResult):
        message = update.telegram_update.message

        insert_fractions = [
            {
                'nickname': x.nickname,
                'fraction': x.fraction,
                'last_update': update.date
            } for x in update.dome.players
        ]

        players_update = Player.insert(insert_fractions) \
            .on_conflict(
            conflict_target=[Player.nickname],
            update={
                Player.fraction: peewee.EXCLUDED.fraction
            },
            where=((Player.fraction != peewee.EXCLUDED.fraction) & (Player.last_update <= peewee.EXCLUDED.last_update))
        ).execute()
        players = Player.select() \
            .where(
            (Player.nickname << [x.nickname for x in update.dome.players]) &
            ((Player.hp != 0) | (Player.attack != 0) | (Player.dzen != 0)) &
            (Player.is_active == False)
        )
        main_text = None
        buttons = []
        for idx, player in enumerate(players, 1):
            if main_text is None:
                main_text = f'<b>It`s Купол Грома лять</b>\n\n{self._generate_text_profile(player)}'
            buttons.append([InlineKeyboardButton(text=f'[{idx}] {player.nickname}', callback_data=f'pvp_profile_{player.id}')])
        if main_text is None:
            main_text = '<b>It`s Купол Грома лять</b>\n\n<code>Ух ля, никого не нашёл(</code>'
        markup = InlineKeyboardMarkup(buttons) if len(buttons) > 1 else None
        self.message_manager.send_message(chat_id=update.invoker.chat_id, text=main_text, parse_mode='HTML', reply_markup=markup)

# ПВП +
# Встреча с фото +
# Встреча "знакомый из фракции" +
# Встреча маньяка +
# Купол грома +

# Линч +
# Убийство покебола +
# Потасовка +
# View ~
