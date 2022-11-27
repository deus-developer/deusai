import random
import telegram
from telegram.ext import Dispatcher
from core import (
    CommandFilter,
    EventManager,
    Handler,
    MessageManager,
    Update
)
from modules import BasicModule
from utils.functions import CustomInnerFilters

ROLLS_TEXTS = '''педор
чмошник
красавчик
милаш
няша
пуся
хуй моржовый
уебашка
дикий
тупенький
генианальный
тварь блядьб
сын маминой подруги
анус ежа
какаха
еблозавр
сволота
жопа
китайский фонарик
конь педальный
сопелька зелёная
хуедрыгало
латентный педераст
питерский гопник
петух гамбургский
петушъя ляжка
задротина
венесуэльская шлюха
гидропидорас натрия
плесень подъяичная
ъуъ сука
Туалетный крякер
Сульфоебанат калия
гусь кастрюльный
Педик обыкновенный
Сопля верблюда
скелебро
ленивый мешок костей
лошок
мать-козе
боженька
Паравозик Дыр-Дыр-Дыр
акулёнок туру ру
дур очка
акула нахуй
арбуэ
алоэ
ебалай
аыаыаыыы
даун
йебанъ
шоколадница
педро гонзалес
йибасио
сосальщик(печеночный)
фуфломицин
хорошЫыый
пьяненький
дед
алкашня
милаха
чудо
прелесть
хил на низком старте
Хомяк
Цезарь
Брут
Иуда
Трус
Балбес
Бывалый
Шурик
super mario
переживший Толину капчу
Толя
Шоколад очка
Дон Педро
Хуаниссимо
Заднеприводный
ГЕЙмер'''.split('\n')


class StartModule(BasicModule):
    """
    start handler
    """
    module_name = 'start'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(
            Handler(
                CommandFilter('start'),
                self._start, custom_filters=[CustomInnerFilters.private]
            )
        )
        self.add_inner_handler(
            Handler(
                CommandFilter('help'),
                self._help, custom_filters=[CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        self.add_inner_handler(
            Handler(
                CommandFilter('rolly'),
                self._rolly, custom_filters=[CustomInnerFilters.from_player, CustomInnerFilters.from_active_chat]
            )
        )
        super().__init__(event_manager, message_manager, dispatcher)

    def _help(self, update: Update):
        """/help в боте"""
        text = '''<b>Справка по использованию Deus AI</b>
        - https://teletype.in/@deusdeveloper/xhu6oDMS6'''
        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text=text,
            parse_mode='HTML'
        )

    def _start(self, update: Update):
        """Приветствие в боте"""
        if not update.player:
            message_text = (
                "Привет, давай знакомиться!\n"
                "Перейди в игру, открой 📟 Пип-бой, "
                "нажми команду <code>/me</code> внизу и перешли мне сообщение с полным профилем"
            )
            markup = telegram.InlineKeyboardMarkup(
                [[telegram.InlineKeyboardButton(text="Перейти в игру", url="https://t.me/WastelandWarsBot")]]
            )
            self.message_manager.send_message(
                chat_id=update.invoker.chat_id, text=message_text, reply_markup=markup,
                parse_mode='HTML'
            )
            return
        keyboard = [
            ['📊 Статы', '📈 Прогресс', '🗓 Рейды'],
        ]

        reply_markup = telegram.ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
        self.message_manager.send_message(chat_id=update.invoker.chat_id, text="Рад тебя видеть", reply_markup=reply_markup)

    def _rolly(self, update: Update):
        roll = random.choice(ROLLS_TEXTS)
        update.telegram_update.message.reply_text(text=f'{update.player} у нас - {roll}')
        update.telegram_update.message.delete()
