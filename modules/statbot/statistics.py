import json
# import pygal

from tempfile import NamedTemporaryFile
from telegram import ChatAction
from telegram.ext import Dispatcher
from core import EventManager, MessageManager, Handler as InnerHandler, UpdateFilter, CommandFilter, Update
from modules import BasicModule
from utils.functions import CustomInnerFilters

class StatisticsModule(BasicModule): #TODO: ПОЛНОСТЬЮ ПЕРЕРАБОТАТЬ

    module_name = 'statistics'

    def __init__(self, event_manager: EventManager, message_manager: MessageManager, dispatcher: Dispatcher):
        pass