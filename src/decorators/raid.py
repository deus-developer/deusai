from functools import wraps

from src.core import InnerUpdate
from src.models.raid_assign import RaidStatus


def get_invoker_raid(func):
    @wraps(func)
    def decorator(self, update: InnerUpdate, *args, **kwargs):
        invoker = update.invoker
        raid = invoker.player.get().actual_raid
        if raid is None or raid.status == RaidStatus.UNKNOWN:
            return self.message_manager.send_message(chat_id=invoker.chat_id, text="Твой пин еще не назначен")

        return func(self, update, raid_assigned=raid, *args, **kwargs)

    return decorator
