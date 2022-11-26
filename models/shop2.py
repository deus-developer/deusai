import peewee
import datetime
from peewee import Model

from models import (
    BaseModel,
    Player
)
from playhouse.postgres_ext import JSONField


class ShopItem(BaseModel, Model):
    id = peewee.AutoField()
    name = peewee.CharField(max_length=255, null=False)
    description = peewee.TextField(default='Этому предмету описание не нужно')
    category = peewee.CharField(
        max_length=30,
        choices=(
            ('DEFAULT', 'default'),
            ('DEUSAI', 'deusai'),
            ('WWITEM', 'wwitem')
        )
    )

    price = peewee.IntegerField(null=False, default=0)
    limit = peewee.IntegerField(null=False, default=0)

    attachment_type = peewee.CharField(
        max_length=255, default='TEXT',
        choices=(
            ('TEXT', 'text'),
            ('PHOTO', 'photo'),
            ('VIDEO', 'video'),
            ('DOCUMENT', 'document'),
        )
    )
    is_auction = peewee.BooleanField(default=False)
    attachment_file_id = peewee.CharField(max_length=255, default='')
    created_date = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        only_save_dirty = True


class ShopPurchase(BaseModel, Model):
    item = peewee.ForeignKeyField(ShopItem, backref='purchares')
    player = peewee.ForeignKeyField(Player, backref='purchares')
    executor = peewee.ForeignKeyField(Player, backref='active_purchares', null=True)

    status = peewee.IntegerField(
        default=0,
        choices=(
            (0, 'OPENED'),
            (1, 'DURING'),
            (2, 'CLOSED'),
            (3, 'REJECTED'),
        )
    )
    price = peewee.IntegerField(default=0)
    message_id = peewee.BigIntegerField(null=False)
    chat_id = peewee.BigIntegerField(null=False)

    created_date = peewee.DateTimeField(default=datetime.datetime.now)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)

    class Meta:
        only_save_dirty = True


class Auction(BaseModel, Model):
    item = peewee.ForeignKeyField(ShopItem, backref='auctions')
    status = peewee.IntegerField(
        default=0, choices=(
            (0, 'OPENED'),
            (1, 'CLOSED'),
        )
    )
    metadata = JSONField()


class AuctionMember(BaseModel, Model):
    auction = peewee.ForeignKeyField(Auction, backref='members')
    player = peewee.ForeignKeyField(Player, backref='auctions')
    price = peewee.IntegerField(default=0)
    last_update = peewee.DateTimeField(default=datetime.datetime.now)
