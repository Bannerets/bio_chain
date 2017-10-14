import matrix
from util import *


class Base():
    def __init__(self, user_id, last, current):
        self.user_id = user_id
        self.last = last
        self.current = current

    def __str__(self):
        return '{} {}: {} -> {}'.format(type(self), self.user_id, self.last, self.current)
        

class Username(Base):
    def shout(self, db):
        shouts = []
        shouts.append(BULLET + '{} has changed their username to {}!'.format(
            markdown_escape(self.last),
            markdown_escape(self.current)
        ))

        for i in range(1, len(db.best_chain)):
            this_id, next_id = db.best_chain[i-1], db.best_chain[i]
            if this_id == self.user_id and db.matrix.get_link_to(this_id, next_id) is not matrix.State.REAL:
                shouts.append(BULLET_2 + '{} should update their bio because of this!'.format(
                    markdown_escape(db.users[next_id])
                ))
                break

        return '\n'.join(shouts)


class Bio(Base):
    def shout(self, db):
        shouts = []
        correct_link_id = 0
        for i in range(1, len(db.best_chain)):
            this_id, next_id = db.best_chain[i-1], db.best_chain[i]

            if this_id == self.user_id:
                correct_link_id = next_id

                if db.matrix.get_link_to(this_id, next_id) is matrix.State.REAL:
                    break
                shouts.append(BULLET + '{}\'s bio should have a link to `{}` but it doesn\'t!'.format(
                    markdown_escape(db.users[self.user_id]),
                    markdown_escape(db.users[next_id], True)
                ))

                if i > 0:
                    break
                shouts.append(BULLET_2 + '{} might want to link to `{}` because of this!'.format(
                    markdown_escape(db.users[db.best_chain[i - 1]]),
                    markdown_escape(db.users[next_id], True)
                ))
                break

        for link_username in self.current:
            link_id = db.translation_table.get(link_username.lower(), None)
            if link_id == correct_link_id or link_id == self.id:
                continue

            warn_username = '@'+link_username
            warn_command = 'might want to'
            if link_id:
                warn_username = str(db.users[self.user_id])
                warn_command = 'should'

            shouts.append(BULLET + '{} {} remove their unnecessary link to `{}`!'.format(
                markdown_escape(db.users[self.user_id]),
                warn_command,
                markdown_escape(warn_username, True)
            ))


        return '\n'.join(shouts)