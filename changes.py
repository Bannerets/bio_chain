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
        return '{}: {} -> {}'.format(self.user_id, self.last, self.current)
        

class Username(Base):
    def shout(self, link_matrix, db, best_chain, dummy):
        shouts = []
        shouts.append(BULLET + '{} has changed their username to {}!'.format(
            username_str(self.last),
            username_str(self.current)
        ))

        for i in range(1, len(best_chain)):
            this_id, next_id = best_chain[i-1], best_chain[i]
            if this_id == self.user_id and link_matrix[this_id][next_id] is not matrix.State.Current:
                shouts.append(BULLET_2 + '{} should update their bio because of this!'.format(
                    username_str(db[next_id]['username'])
                ))
                break

        return '\n'.join(shouts)


class Bio(Base):
    def shout(self, link_matrix, db, best_chain, username_to_id):
        shouts = []
        correct_link_id = 0
        for i in range(1, len(best_chain)):
            prev_id, this_id = best_chain[i-1], best_chain[i]

            if this_id == self.user_id:
                correct_link_id = prev_id

                if link_matrix[prev_id][this_id] is matrix.State.Current:
                    break
                shouts.append(BULLET + '{}\'s bio should have a link to `{}` but it doesn\'t!'.format(
                    username_str(db[self.user_id]['username']),
                    username_str(db[prev_id]['username'])
                ))

                if i == len(best_chain) - 1:
                    break
                shouts.append(BULLET_2 + '{} might want to link to `{}` because of this!'.format(
                    username_str(db[best_chain[i + 1]]['username']),
                    username_str(db[prev_id]['username'])
                ))
                break

        for link_username in self.current:
            link_id = username_to_id.get(link_username.lower(), 0)
            if link_id and link_id != correct_link_id:
                shouts.append(BULLET + '{} should remove their unnecessary link to `{}`!'.format(
                    username_str(db[self.user_id]['username']),
                    username_str(db[link_id]['username'])
                ))


        return '\n'.join(shouts)
        