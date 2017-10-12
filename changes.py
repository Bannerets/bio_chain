import matrix
from util import *

BULLET = '∙ '
BULLET_2 = '  - '


class Base():
    def __init__(self, user_id, last, current):
        self.user_id = user_id
        self.last = last
        self.current = current

    def __str__(self):
        return '{} {}: {} -> {}'.format(type(self), self.user_id, self.last, self.current)
        

class Username(Base):
    def shout(self, db):
        return 'USERNAME ' + str(self)


class Bio(Base):
    def shout(self, db):
        return 'BIO ' + str(self)
        