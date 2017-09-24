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
            link_matrix[user_id][link] = State.Old

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
            if link_matrix[user_id][link] is not State.Empty:
                new_links.add(link)

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
    """Returns a list of all valid links of user_id to other users (ie all the users linked from user_id)"""
    links = []
    for link_id in link_matrix:
        if link_matrix[link_id][user_id] is State.Current:
            links.append(link_id)
    return links