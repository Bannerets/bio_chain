import changes
import html
import requests
import re
from util import *
import telegram

RE_SCRAPE_BIO = re.compile(r'<meta +property="og:description" +content="(.+?)".*>')
RE_USERNAME = re.compile(r'@([a-zA-Z][\w\d]{4,31})')

class User():
    defaults = {
        'bio': [],
        'joined': None,
        'expires': 0,
        'disabled': False,
    }

    def __init__(self, user_id, data):
        self.id = user_id
        self.username = data['username']
        self.username_fetch_failed = False

        for key, default_val in self.defaults.items():
            setattr(self, key, data.get(key, default_val))


    def __str__(self):
        #todo: handle blank usename better
        return '@' + self.username if self.username else f'[no username: {self.id}]'


    def str_with_id(self):
        return f'{self} [{self.id}]' if self.username else str(self)


    def is_expired(self):
        return self.expires < get_current_timestamp()


    def reset_expiry(self):
        self.expires = get_current_timestamp() + 240
        return True


    def to_dict(self):
        result = {}
        result['username'] = self.username
        for key, default_val in self.defaults.items():
            current_val = getattr(self, key)
            if current_val != default_val:
                result[key] = current_val
        return result


    def update_username(self, bot):
        pending_changes = []

        try:
            new_username = bot.getChatMember(CHAT_ID, self.id).user.username or ''
            if new_username != self.username:
                old_username_str = str(self)
                self.username = new_username
                if old_username_str.lower() != str(self).lower():
                    pending_changes.append( changes.Username(self.id, old_username_str, str(self)) )
        except telegram.error.TimedOut:
            print('  Timed out fetching username')
        except Exception as e:
            self.username_fetch_failed = True
            print('  Failed to fetch username', type(e))

        return pending_changes

    def update_bio(self):
        if not self.username:
            print(f'  Tried to scrape blank username')
            return []

        r = requests.get(f'http://t.me/{self.username}')
        if not r.ok:
            print(f'  Request for bio failed ({r.status_code})')
            return []

        bio = RE_SCRAPE_BIO.findall(r.text)
        if not bio:
            print('  Failed to scrape bio tag')
            return []

        new_bio = {}
        for bio_username in RE_USERNAME.findall(html.unescape(bio[0])):
            if bio_username.lower() == self.username.lower():
                continue
            new_bio[bio_username.lower()] = bio_username

        pending_changes = []
        new_bio = [v for k, v in new_bio.items()]
        if not caseless_set_eq(new_bio, self.bio):
            pending_changes.append( changes.Bio(self.id, self.bio, new_bio) )
            self.bio = new_bio

        return pending_changes

    def try_update(self, bot):
        pending_changes = []
        pending_changes.extend(self.update_username(bot))
        pending_changes.extend(self.update_bio())
        self.reset_expiry()
        return pending_changes



if __name__ == '__main__':
    user = User(420, {'username': 'test_user'})
    assert user.id == 420
    assert user.username == 'test_user'
    assert user.is_expired() == True
    user.reset_expiry()
    assert user.is_expired() == False

    print(user)
    user = User(69, {'username': ''})
    print(user)