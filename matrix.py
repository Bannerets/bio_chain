from enum import Enum
from collections import defaultdict
import json



class State(Enum):
    """
    State of a link:
    Old: The link has existed in the past but does not exist right now
    Empty: There's no link here
    Current: The link exists right now
    """
    Old = -1
    Empty = 0
    Current = 1



def new_empty():
    return defaultdict(
        lambda: defaultdict(
            lambda: State.Empty
        )
    )



def from_db(db):
    """Builds a link matrix from db"""

    link_matrix = new_empty()
    for user_id, data in db.items():
        for link in data.get('linked_by', []):
            state = State.Current
            if link[0] == '!':
                state = State.Old
                link = link[1:]

            link_matrix[user_id][link] = state

    return link_matrix



def update_db(link_matrix, db):
    """
    Modifies db with new data from link_matrix
    Returns True if any change has been made to db
    """
    modified = False

    for user_id in link_matrix:
        new_links = set()

        for link in link_matrix[user_id]:
            state = link_matrix[user_id][link]
            if state is State.Current:
                new_links.add(link)
            elif state is State.Old:
                new_links.add('!'+link)

        if new_links != set(db[user_id].get('linked_by', [])):
            db[user_id]['linked_by'] = list(new_links)
            modified = True


    return modified



def debug_print(link_matrix, db):
    """Prints link_matrix in a grid"""
    padding = 0
    for user_id, data in db.items():
        if len(data['username']) > padding:
            padding = len(data['username'])
    padding += 2

    print(' ' * (padding+1), end='')
    i = 0
    for key in db:
        print('{0: >2} '.format(chr(i + 65)), end='')
        i += 1
    print()


    i = 0
    for basekey in db:
        print('{} {}'.format(chr(i + 65), db[basekey]['username']).ljust(padding) + ':', end='')
        for key in db:
            print('{0: >2} '.format(link_matrix[basekey][key].value), end='')
        print()
        i += 1



def get_links_to(link_matrix, user_id):
    """Returns a list of all valid links that user_id has to other users"""
    links = []
    for link_id in link_matrix:
        if link_matrix[link_id][user_id] is State.Current:
            links.append(link_id)
    return links


def has_valid_link(link_matrix, user_id):
    """Returns true if user_id has a valid link, false if not"""
    for link_id in link_matrix:
        if link_matrix[link_id][user_id] is State.Current:
            return True
    return False
