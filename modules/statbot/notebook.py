import datetime

from pytils import dt
from telegram.ext import Dispatcher

from config import settings
from core import (
    EventManager,
    Handler as InnerHandler,
    MessageManager,
    Update,
    UpdateFilter
)
from models import Notebook
from modules import BasicModule


class NotebookModule(BasicModule):  # TODO: Добавить человекочитаеммое форматирование
    module_name = 'notebook'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(UpdateFilter('notebook'), self._parse_notebook))
        super().__init__(event_manager, message_manager, dispatcher)

        self.KEY_BY_NAME = {
            '👣Пройдено': 'passed',
            '⚔️Убито': 'kills_pve',
            '🔪Побеждено': 'kills_pvp',
            '👁Ударил гиганта': 'hit_giant',
            '⚜️Побеждено': 'win_boss',
            '😰Сбежал от': 'escaped',
            '👊Участвовал в': 'participated',
            '💉Использовано': 'used_stim',
            '💊Использовано': 'used_speeds',
            '🚫Сломано': 'broken_things',
            '🕵️Выполнено': 'completed_assignments',
            '🎁Открыто': 'open_gifts',
            '🎁Отправлено': 'send_gifts',
            '🗳Открыто': 'open_randbox',
            '📯Пройдено': 'dange_completed',
            '⚠️Прошел пещеру': 'passed_cave',
            '⚠️Не прошел пещеру': 'not_passed_cave',
            '⚡️Под куполом': 'win_of_dome',
            '📢Пригласил': 'invited',
            '🗄Разобрал': 'open_box',
            '⚰️Умер': 'deads',
        }

    def _parse_notebook(self, update: Update):
        notebook = update.notebook
        now = datetime.datetime.now()
        timeout = datetime.timedelta(seconds=10)

        if update.timedelta >= timeout:
            return

        if now - update.player.last_update < timeout:
            return

        if not update.player.notebook:
            update.player.notebook = Notebook.create(last_update=timeout - datetime.timedelta(seconds=10))
            update.player.save()

        if update.player.notebook.last_update > update.telegram_update.message.forward_date.astimezone(settings.timezone):
            return self.message_manager.send_message(
                chat_id=update.telegram_update.message.chat_id,
                text='Ты пытаешься отправить более старый дневник.'
            )
        delts = []
        for name, value, name2 in notebook.attrs:
            key = self.KEY_BY_NAME.get(name, 'buffer')
            last = getattr(update.player.notebook, key)
            if key == 'buffer' or (value - last) <= 0:
                continue
            delts.append([name, value - last, name2])
            setattr(update.player.notebook, key, value)

        output = ['\t<b>Обновление дневника:</b>']
        for name, delta, name2 in delts:
            output.append(f'{name} <em>+{delta}</em><i>{name2}</i>')
        if len(output) == 1:
            output.append('\t\t\t<i>Ой, а где оно?</i>')

        output.append(f'\n\t<i><code>Последнее изменение: {dt.distance_of_time_in_words(update.player.notebook.last_update, accuracy=3)}</code></i>')
        self.message_manager.send_message(
            chat_id=update.telegram_update.message.chat_id,
            text='\n'.join(output),
            parse_mode='HTML'
        )
        update.player.notebook.last_update = update.date
        update.player.notebook.save()
