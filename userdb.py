import json
import telegram
from collections import defaultdict
import time

USERDB_FILENAME = 'users.json'



class User(object):
    """
    Keeps track if each user's username and if the username needs to be fetched again
    """
    def __init__(self, username):
        self.expires = 0
        self.username = username

    def is_expired(self):
        return time.time() > self.expires

    def reset_expiry(self, seconds=60):
        self.expires = time.time() + seconds

    def update_username(self, username, reset=True):
        """Updates the username associated with this user, returns True if the username has changed"""
        if username is None:
            return False

        if reset:
            self.reset_expiry(60)
        if username.lower() != self.username.lower():
            print(f'{self.username} -> {username}')
            self.username = username
            return True
        return False



def new():
    return defaultdict(lambda: User(''))



def load():
    """Updates user database with data from USERDB_FILENAME"""
    with open(USERDB_FILENAME) as f:
        data = json.load(f)

    userdb = new()
    for user_id, username in data.items():
        userdb[user_id].update_username(username, reset=False)

    return userdb



def save(userdb):
    """Dumps the user database to USERDB_FILENAME as JSON"""
    out = {user_id: user.username for user_id, user in userdb.items()}

    with open(USERDB_FILENAME, 'w') as f:
        json.dump(out, f)



def usernames_to_id(userdb, usernames):
    """
    Attempts to get the ID for the given usernames by checking in the userdb.
    Returns the ids of the users.
    """

    ids = []
    for username in usernames:
        for this_id, this_user in userdb.items():
            if username.lower() == this_user.username.lower():
                ids.append(this_id)

    return ids