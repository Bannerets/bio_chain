import re
import json
import telegram
import requests
import html
from collections import defaultdict
import time

USERDB_FILENAME = 'users.json'
RE_SCRAPE_BIO = re.compile(r'<meta +property="og:description" +content="(.+?)".*>')
RE_USERNAME = re.compile(r'@([a-zA-Z][\w\d]{4,31})')



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



def username_to_id(userdb, username):
    """
    Attempts to get the ID for the given username by checking in the userdb.
    Returns the id of the user (may be None if not found).
    """

    for this_id, this_user in userdb.items():
        if username.lower() == this_user.username.lower():
            return this_id



def get_link_ids_from_bio(userdb, username):
    """
    Scrapes the bio from t.me/username
    Returns a list of user_ids of all valid links to users that we know
    """

    r = requests.get(f'http://t.me/{username}')
    if not r.ok:
        print(f"Request for @{username}'s bio failed")
        return []

    bio = RE_SCRAPE_BIO.findall(r.text)
    if not bio:
        return []
    bio = html.unescape(bio[0])
    link_names = RE_USERNAME.findall(bio)
    
    link_ids = []
    for link_name in link_names:
        link_id = username_to_id(userdb, link_name)
        if link_id:
            link_ids.append(link_id)

    return link_ids