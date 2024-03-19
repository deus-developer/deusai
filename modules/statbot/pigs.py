import datetime
import html
import random
from typing import List, Optional

import peewee
from telegram.ext import Dispatcher

from core import EventManager, MessageManager, InnerHandler, InnerUpdate, CommandFilter
from decorators import command_handler, get_chat, get_pig
from models import Pig
from modules import BasicModule


class PigsModule(BasicModule):
    module_name = 'pigs'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            InnerHandler(
                CommandFilter('pgrow'),
                self.pig_grow
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('pname'),
                self.pig_name
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('pfight'),
                self.pig_fight
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('mypig'),
                self.pig_my
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('pigtop'),
                self.pig_top
            )
        )

        self.add_inner_handler(
            InnerHandler(
                CommandFilter('phelp'),
                self.pig_help
            )
        )

        super().__init__(event_manager, message_manager, dispatcher)

    def missing_pig(self, update: InnerUpdate):
        text = (
            'Ты ещё не завел своего хряка?\n'
            'Начни играть, написав в чате "/pgrow имя хряка".'
        )
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    def missing_chat(self, update: InnerUpdate):
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text='Эту команду нужно слать в чате'
        )

    def is_valid_pig_name(self, name: str) -> bool:
        is_valid_len = 3 <= len(name) <= 32
        return is_valid_len

    def pig_create(self, update: InnerUpdate, name: str):
        if not self.is_valid_pig_name(name):
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f'{html.escape(name)} не валидное имя хряка.'
            )

        pig = Pig.create(
            telegram_user=update.invoker,
            telegram_chat=update.chat,
            name=name,
            weight=0,
            last_grow_at=datetime.datetime.min
        )
        text = (
            f'Добро пожаловать в игру, {update.invoker.mention_html()}.\n'
            f'Твоего хряка зовут: {html.escape(pig.name)}\n\n'
            'И далее используй команду /pgrow, чтобы выращивать своего хряка.'
        )
        self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )
        return pig

    def pig_grow_wait_day(self, update: InnerUpdate):
        text = (
            f'{update.invoker.mention_html()}, '
            'вы уже кормили своего свинтуса сегодня.'
        )
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    @command_handler()
    @get_pig
    def pig_grow(self, update: InnerUpdate):
        if update.chat is None:
            return self.missing_chat(update)

        if update.command.argument and update.pig is None:
            update.pig = self.pig_create(update, update.command.argument)
        elif update.pig is None:
            return self.missing_pig(update)

        if update.pig.feeded:
            return self.pig_grow_wait_day(update)

        weight_boost = sum(
            random.randint(1, offset)
            for offset in range(10, 50 + 1, 10)
        )

        query = (
            Pig.update(
                weight=Pig.weight + weight_boost,
                last_grow_at=datetime.datetime.now()
            )
            .where(
                Pig.telegram_user == update.invoker,
                Pig.telegram_chat == update.chat
            )
            .returning(Pig.weight)
            .dicts()
            .execute()
        )

        weight: Optional[int] = None
        for row in query:
            weight = row['weight']

        if weight is None:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text='Упс... 🐽 Хряк не вырос.'
            )

        text = (
            f'{update.invoker.mention_html()}, ваш 🐽 Хряк поправился на {weight_boost} кг сала!\n'
            f'Масса вашего пиглета: {weight} кг'
        )

        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    @command_handler()
    @get_pig
    def pig_name(self, update: InnerUpdate):
        if update.chat is None:
            return self.missing_chat(update)

        if update.pig is None:
            return self.missing_pig(update)

        if update.command.argument is None:
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text='Чтобы назвать своего свинтуса введи "/pname имя хряка".'
            )

        name = update.command.argument
        if not self.is_valid_pig_name(name):
            return self.message_manager.send_message(
                chat_id=update.effective_chat_id,
                text=f'{html.escape(name)} не валидное имя хряка.'
            )

        query = (
            Pig.update(
                name=name
            )
            .where(
                Pig.telegram_user == update.invoker,
                Pig.telegram_chat == update.chat
            )
        )
        query.execute()

        text = (
            f'Новое имя твоего хряка : 🐷 {html.escape(name)}  🐷.\n\n'

            'Носи его с честью.'
        )
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    @get_pig
    def pig_my(self, update: InnerUpdate):
        if update.chat is None:
            return self.missing_chat(update)

        if update.pig is None:
            return self.missing_pig(update)

        pig = update.pig

        if pig.feeded:
            feed_text = 'покормлен'
        else:
            feed_text = 'не покормлен'

        text = (
            f'Харакетристики твоего 🐷 {html.escape(pig.name)}:\n\n'

            f'🪶 масса: {pig.weight}кг\n'
            f'💥 Шанс крита: {pig.critical_chance}%\n\n'

            'Текущее настроение свина: так и хочет задавить кого-то\n'
            f'🐖 Свин {feed_text}\n'
            '👊 Готов сражаться'
        )
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    @get_chat
    def pig_top(self, update: InnerUpdate):
        if update.chat is None:
            return self.missing_chat(update)

        query = (
            Pig.select(
                Pig.name,
                Pig.weight,
                peewee.fn.dense_rank().over(
                    order_by=[Pig.weight.desc()]
                ).alias('idx')
            )
            .where(
                Pig.telegram_chat == update.chat
            )
            .order_by(Pig.weight.desc())
            .limit(10)
            .dicts()
        )

        rating: List[str] = []
        for row in query:
            position = row['idx']
            name = row['name']
            weight = row['weight']

            rating.append(f'{position}. {html.escape(name)} - {weight}кг')

        rating_text = '\n'.join(rating)

        text = (
            '🐖 Зал славы хряков 🐖\n\n'

            f'{rating_text}'
        )
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    def pig_help(self, update: InnerUpdate):
        text = (
            '/mypig - позволяет тебе посмотреть характеристики твоего драгоценного порося.\n\n'

            '/pigtop - открывает зал славы вашего свинарника.\n\n'

            '/pgrow - ты можешь кормить своего хряка раз в день.\n\n'

            'Чем меньше кг за день наел хряк, тем он злее (выше шанс крита).\n'
            'Чем свин тяжелее оппонента, тем выше его защита в бою (труднее по тебе попасть)\n'
            'Чем выше у хряка шанс крита тем проще ему пустить противника на фарш.\n\n'

            '/pfight - ты можешь встать в очередь на бой или выйти из нее.\n'
            'Разобраться в бою тебе помогут обозначения:\n'
            '🩸 - успешная атака;\n'
            '🩸🩸 - критическая атака;\n'
            '🛡 - успешная защита;\n'
            '⁉️ - парирование (контратака).\n\n'

            'Всего в бою у свиньи три жизни.\n'
            'Атака снимает одну жизнь, критическая атака снимает две.\n'
            'Побеждает свин первым снявший три жизни оппонента.'
        )
        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text=text
        )

    @get_pig
    def pig_fight(self, update: InnerUpdate):
        if update.chat is None:
            return self.missing_chat(update)

        if update.pig is None:
            return self.missing_pig(update)

        return self.message_manager.send_message(
            chat_id=update.effective_chat_id,
            text='🧑‍💻 В разработке...'
        )
