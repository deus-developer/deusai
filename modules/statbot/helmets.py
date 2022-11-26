import re
import json
import glob
from PIL import Image
from core import EventManager, MessageManager, Handler as InnerHandler, CommandFilter, UpdateFilter, Update
from tempfile import NamedTemporaryFile
from modules.statbot.parser import PlayerParseResult
from telegram.ext import Dispatcher
from decorators import command_handler, permissions
from decorators.permissions import is_admin
from modules import BasicModule
from utils.functions import CustomInnerFilters

class HelmetsModule(BasicModule): #TODO: ПОЛНОСТЬЮ ПЕРЕРАБОТАТЬ
    """
    message sending
    """
    module_name = 'helmets'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        self.add_inner_handler(InnerHandler(UpdateFilter('meeting'), self._meeting_handler))

        helmets_ = glob.glob('files/configs/helmets/*.json')
        armors_ = glob.glob('files/configs/armors/*.json')

        self.helmets = [json.load(open(file, 'r', encoding='utf-8')) for file in helmets_]
        self.armors = [json.load(open(file, 'r', encoding='utf-8')) for file in armors_]

            
        super().__init__(event_manager, message_manager, dispatcher)

    def compare_colors(self, color1, color2, c: int = 40):
        for i in range(3):
            if not (color1[i][0]-c <= color2[i] <= color1[i][1]+c):
                return False
        return True

    def search_item(self, items_, pixels):
        for item in items_:
            pixels_ = item.get('pixels', None)
            if not pixels_:
                continue
            is_item = all([self.compare_colors(pixel[2], pixels[pixel[0], pixel[1]]) for pixel in pixels_])
            if is_item:
                return item
        return False

    def _meeting_handler(self, update: PlayerParseResult):
        message = update.telegram_update.message
        if not message.photo:
            return
        tmp = self.download_file(message.photo[-1])
        if not tmp:
            return
        image = Image.open(tmp.name)
        pixels = image.load()

        helmet = self.search_item(self.helmets, pixels)
        armor = self.search_item(self.armors, pixels)
        tmp.seek(0)
        if not (armor or helmet):
            return
        sum_armor = 0

        formatted_text = (
                'Я вижу на нём.....\n'
            )
        if helmet:
            a = helmet.get('armor', 0)
            sum_armor += a
            formatted_text += (
                    f'{helmet.get("name", "Неизвестность")}({a}🛡)\n'
                )
        if armor:
            a = armor.get('armor', 0)
            sum_armor += a
            formatted_text += (
                    f'{armor.get("name", "Неизвестность")}({a}🛡)\n'
                )

        formatted_text += (
                f'Всего: {sum_armor}🛡'
            )
        self.message_manager.send_message(  chat_id=message.chat_id,
                                            reply_to_message_id=message.message_id,
                                            text=formatted_text)

    def download_file(self, object_):
        file = object_.get_file()
        tmp = NamedTemporaryFile()
        try:
            file.download(custom_path=tmp.name)
        except:
            self.logger.warning(f'Ошибка скачивания файла {file.file_id}')
            return False
        return tmp