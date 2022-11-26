import datetime
import peewee

from .base import BaseModel
from models import Player


class Item(BaseModel):
    id = peewee.BigAutoField(unique=True, primary_key=True, index=True, null=False)
    name = peewee.CharField(max_length=255, null=False, unique=True)
    type = peewee.CharField(max_length=255, null=False)

    class Meta:
        only_save_dirty = True


class InventoryItem(BaseModel):
    owner = peewee.ForeignKeyField(Player, backref='inventory', null=False)
    item = peewee.ForeignKeyField(Item, backref='inventories', null=False)
    amount = peewee.IntegerField(null=False, default=0)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    @classmethod
    def get_by_item(cls, item: Item, player: Player):
        in_inventory = cls.select().where((cls.owner == player) & (cls.item == item))
        if in_inventory:
            return in_inventory.get(), False
        return cls.create(
            owner=player,
            item=item
        ), True

    class Meta:
        only_save_dirty = True
