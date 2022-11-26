import datetime
import logging
import threading
import time
from collections import (
    deque,
    namedtuple
)
from queue import PriorityQueue
import telegram
from apscheduler.schedulers.background import BackgroundScheduler

CallbackResults = namedtuple('CallbackResults', ['value', 'error', 'args'])


class RowFunctionArgs(object):
    """
    wraps arguments for PriorityQueue
    """

    def __init__(
        self, foo: callable, priority=1, callback: callable = None,
        callback_args=None, args=None, kwargs=None, group=False
    ):
        self.priority = priority
        self.foo = foo
        self.callback = callback
        self.callback_args = callback_args
        self.args = args
        self.kwargs = kwargs
        self.group = group

    def __lt__(self, other):
        return self.priority < other.priority


class MessageManager:
    #  see https://github.com/python-telegram-bot/python-telegram-bot/wiki/Avoiding-flood-limits
    def __init__(self, bot: telegram.Bot, scheduler: BackgroundScheduler, all_burst_limit=30, group_burst_limit=20):
        """unlike normal telegram Bot de not return anything valuable after calling send
        if value is needed send it's receiver as a callback argument, or set is_queued parameter to False"""
        self.logger = logging.getLogger(__name__)

        self._burst_limit = all_burst_limit  # messages per second
        self._group_burst_limit = group_burst_limit  # messages per minute

        self._m_deque = deque()  # times to invoke self._call() under burst limit
        self._mg_deque = deque()  # same with groups
        self._m_blocked = False
        self._mg_blocked = False
        self._mq = PriorityQueue()
        self._mq_group = PriorityQueue()

        self.bot = bot
        self._scheduler = scheduler
        self._updates = {}
        self._lock = threading.RLock()
        self._scheduler.add_job(self.run, 'interval', seconds=2)

    def _call(self, group=False):
        i = None
        if not group and not self._mq.empty():
            i = self._mq.get()
        elif group and not self._mq_group.empty():
            i = self._mq_group.get()
            self._mg_deque.append(time.time())

        self._m_deque.append(time.time())
        if i:
            try:
                res = i.foo(*i.args, **i.kwargs)
            except telegram.TelegramError as e:
                self.logger.error(e.message)
                if i.callback:
                    i.callback(CallbackResults(None, e, i.callback_args))
            else:
                if i.callback:
                    i.callback(CallbackResults(res, None, i.callback_args))

    def _empty(self):
        return self._mq.empty() and self._mq_group.empty()

    def _plan_next(self):
        now = time.time()
        if self._empty():
            return
        while len(self._mg_deque) and now - self._mg_deque[0] > 60:
            self._mg_deque.pop()
        while len(self._m_deque) and now - self._m_deque[0] > 1:
            self._m_deque.pop()
        while not self._mq.empty() and len(self._m_deque) < self._burst_limit:
            self._m_blocked = False
            self._call(False)
        while not self._mq_group.empty() \
                and len(self._m_deque) < self._burst_limit and len(self._mg_deque) < self._group_burst_limit:
            self._m_blocked = False
            self._mg_blocked = False
            self._call(True)
        if self._m_blocked:
            return
        if not self._mq.empty():
            self._m_blocked = True
            d = 1.01 - now + self._m_deque[0]
            self._scheduler.add_job(
                self._plan_next,
                'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=d)
            )
        if self._mg_blocked:
            return
        if not self._mq_group.empty():
            self._mg_blocked = True
            d = 60.01 - now + self._m_deque[0]
            self._scheduler.add_job(
                self._plan_next,
                'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=d)
            )

    def send_message(self, is_queued=True, callback: callable = None, callback_args=None, priority=1, *args, **kwargs):
        # if settings.DEBUG or settings.TESTING and 'chat_id' in kwargs:  # in debug mode send messages only to admin
        #     kwargs['chat_id'] = settings.ADMIN_CHAT_ID # Nope it's not good for testing

        if not is_queued:
            self._m_deque.append(time.time())
            if kwargs.get('chat_id') and kwargs.get('chat_id') < 0:
                self._mg_deque.append(time.time())
            return self.bot.send_message(*args, **kwargs)
        if not kwargs.get('chat_id'):
            self.logger.warning(f'args {args}\t kwargs {kwargs}')
        if kwargs.get('chat_id') and kwargs.get('chat_id') < 0:
            self._mq_group.put(
                RowFunctionArgs(
                    self.bot.send_message,
                    priority, callback, callback_args, args, kwargs, False
                )
            )
            self._plan_next()
        else:
            self._mq.put(
                RowFunctionArgs(
                    self.bot.send_message,
                    priority, callback, callback_args, args, kwargs, True
                )
            )
            self._plan_next()

    def send_split(self, msg, chat_id, n, reply=False):
        split = msg.split('\n')
        for i in range(0, len(split), n):
            text = ('...\n' if i != 0 else '') + '\n'.join(split[i:min(i + n, len(split))])
            time.sleep(1. / 30)
            kwargs = {
                'reply_to_message_id': reply
            } if reply else {}
            self.send_message(
                chat_id=chat_id, text=text, parse_mode='HTML',
                disable_web_page_preview=True, **kwargs
            )

    def pin(self, chat_id, text, uid, silent=False):
        mid = 0
        try:
            mid = self.send_message(is_queued=False, chat_id=chat_id, text=text, parse_mode='HTML').message_id
        except (Exception, ):
            pass

        time.sleep(0.5)
        if not mid:
            self.send_message(chat_id=uid, text="Не удалось доставить сообщение")
            return

        try:
            self.bot.pin_chat_message(chat_id=chat_id, message_id=mid, disable_notification=silent)
        except (Exception, ):
            self.send_message(chat_id=uid, text="Я не смог запинить((")
            return

        self.send_message(chat_id=uid, text="Готово\nСообщение в пине")

    def update_msg(self, *args, **kwargs):
        with self._lock:
            self._updates[(kwargs['chat_id'], kwargs['message_id'])] = (args, kwargs)

    def run(self):
        with self._lock:
            ups = list(self._updates.values())
            self._updates.clear()
        for up in ups:
            self._update_msg(*up[0], **up[1])

    def _update_msg(self, *args, **kwargs):
        try:
            return self.bot.edit_message_text(*args, **kwargs)
        except (Exception, ):
            pass
