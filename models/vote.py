import peewee
import datetime
from peewee import Model

from models import (
    BaseModel,
    Player
)

ThroughDeferredVoted = peewee.DeferredThroughModel()


class Vote(BaseModel, Model):
    id = peewee.AutoField()
    subject = peewee.CharField(max_length=255, null=False, index=True)
    invoker = peewee.ForeignKeyField(Player, backref='votes_invoked')
    complete = peewee.BooleanField(default=False)
    created_date = peewee.DateTimeField(default=datetime.datetime.now)
    enddate = peewee.DateTimeField(default=datetime.datetime.now)
    type = peewee.IntegerField(default=0)

    def __str__(self):
        return f'[{str(self.invoker)}]: {self.subject}'

    class Meta:
        only_save_dirty = True


class VoteAnswer(BaseModel, Model):
    id = peewee.AutoField()
    vote = peewee.ForeignKeyField(Vote, backref='answers')
    title = peewee.CharField(max_length=255, null=False, index=True)

    voted = peewee.ManyToManyField(Player, backref='votes', through_model=ThroughDeferredVoted)

    class Meta:
        only_save_dirty = True


class AnswerPlayerThrough(BaseModel, Model):
    player = peewee.ForeignKeyField(Player)
    answer = peewee.ForeignKeyField(VoteAnswer)

    class Meta:
        table_name = 'answer_player_through'


ThroughDeferredVoted.set_model(AnswerPlayerThrough)
