import datetime
import logging
import threading
import time
from collections import deque, namedtuple
from queue import PriorityQueue
from typing import Optional

import telegram
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import ParseMode, Message

logger = logging.getLogger(__name__)

CallbackResults = namedtuple('CallbackResults', ['value', 'error', 'args'])


class RowFunctionArgs(object):
    """
    wraps arguments for PriorityQueue
    """

    def __init__(
        self,
        foo: callable,
        priority=1,
        callback: callable = None,
        callback_args=None,
        args=None,
        kwargs=None,
        group=False
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
                logger.error(e.message)
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

        while (
            not self._mq_group.empty() and
            len(self._m_deque) < self._burst_limit and
            len(self._mg_deque) < self._group_burst_limit
        ):
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
                'date',
                run_date=datetime.datetime.now() + datetime.timedelta(seconds=d)
            )

        if self._mg_blocked:
            return

        if not self._mq_group.empty():
            self._mg_blocked = True
            d = 60.01 - now + self._m_deque[0]
            self._scheduler.add_job(
                self._plan_next,
                'date',
                run_date=datetime.datetime.now() + datetime.timedelta(seconds=d)
            )

    def reply_message(
        self,
        message: Message,
        is_queued: bool = True,
        callback: callable = None,
        callback_args=None,
        priority: int = 1,
        *args,
        **kwargs
    ):
        kwargs.setdefault('reply_to_message_id', message.message_id)
        kwargs.setdefault('chat_id', message.chat_id)

        return self.send_message(
            is_queued=is_queued,
            callback=callback,
            callback_args=callback_args,
            priority=priority,
            *args,
            **kwargs
        )

    def send_message(
        self,
        is_queued: bool = True,
        callback: callable = None,
        callback_args=None,
        priority: int = 1,
        *args,
        **kwargs
    ):
        kwargs.setdefault('parse_mode', ParseMode.HTML)
        kwargs.setdefault('disable_web_page_preview', True)

        if not is_queued:
            self._m_deque.append(time.time())
            if kwargs.get('chat_id') and kwargs.get('chat_id') < 0:
                self._mg_deque.append(time.time())
            return self.bot.send_message(*args, **kwargs)

        if kwargs.get('chat_id') and kwargs.get('chat_id') < 0:
            self._mq_group.put(RowFunctionArgs(
                self.bot.send_message,
                priority, callback, callback_args, args, kwargs, False
            ))
        else:
            self._mq.put(RowFunctionArgs(
                self.bot.send_message,
                priority, callback, callback_args, args, kwargs, True
            ))

        self._plan_next()

    def send_message_splitted(
        self,
        text: str,
        chat_id: int,
        n: int,
        reply_to_message_id: Optional[int] = None
    ):
        split = text.split('\n')
        for i in range(0, len(split), n):
            text = ('...\n' if i != 0 else '') + '\n'.join(split[i:min(i + n, len(split))])
            time.sleep(1. / 30)
            kwargs = {'reply_to_message_id': reply_to_message_id} if reply_to_message_id else {}
            self.send_message(
                chat_id=chat_id,
                text=text,
                disable_web_page_preview=True,
                **kwargs
            )

    def edit_message_text(self, *args, **kwargs):
        with self._lock:
            self._updates[(kwargs['chat_id'], kwargs['message_id'])] = (args, kwargs)

    def run(self):
        with self._lock:
            ups = list(self._updates.values())
            self._updates.clear()

        for args, kwargs in ups:
            self._edit_message_text(*args, **kwargs)

    def _edit_message_text(self, *args, **kwargs):
        try:
            return self.bot.edit_message_text(*args, **kwargs)
        except (Exception,):
            pass
