from enum import Enum
from collections import defaultdict
import json

LINKS_FILENAME = 'links.json'



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



def new():
    return defaultdict(
        lambda: defaultdict(
            lambda: State.Empty
        )
    )



def load():
    """Updates link_matrix in place with the entries from LINKS_FILENAME"""
    with open(LINKS_FILENAME) as f:
        data = json.load(f)

    link_matrix = new()
    for user_id, links in data.items():
        for link in links:
            link_matrix[user_id][link] = State.Old

    return link_matrix



def save(link_matrix):
    """Dumps link_matrix to LINKS_FILENAME"""
    out = defaultdict(list)

    for user_id in link_matrix:
        for link_id in link_matrix[user_id]:
            if link_matrix[user_id][link_id] is not State.Empty:
                out[user_id].append(link_id)

    with open(LINKS_FILENAME, 'w') as f:
        json.dump(out, f)



def print(link_matrix, userdb):
    """Prints link_matrix in a grid"""
    padding = 0
    for user_id, user in userdb.items():
        if len(user.username) > padding:
            padding = len(user.username)
    padding += 2

    print(' ' * (padding+1), end='')
    i = 0
    for key in userdb:
        print('{0: >2} '.format(chr(i + 65)), end='')
        i += 1
    print()


    i = 0
    for basekey in userdb:
        print('{} {}'.format(chr(i + 65), userdb[basekey].username).ljust(padding) + ':', end='')
        for key in userdb:
            print('{0: >2} '.format(link_matrix[basekey][key].value), end='')
        print()
        i += 1



def user_has_valid_link(user_id, link_matrix):
    """Returns true if user_id has at least one link"""
    for link_id in link_matrix[user_id]:
        if link_matrix[user_id][link_id] is State.Current:
            return True
    return False



def get_links_to(link_matrix, user_id):
    """Returns a list of user_ids that currently link to user_id"""
    return [link_id for link_id in link_matrix if link_matrix[link_id][user_id] is State.Current]
