from util import *

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

    #todo: handle blank usename better
    def __str__(self):
        return '@' + self.username if self.username else f'[no username: {self.id}]'

    def str_with_id(self):
        return f'{self} [{self.id}]' if self.username else str(self)

    def is_expired(self):
        return self.expires < get_current_timestamp()

    def reset_expiry(self):
        self.expires = get_current_timestamp() + 60
        return True

    def to_dict(self):
        result = {}
        result['username'] = self.username
        for key, default_val in self.defaults.items():
            current_val = getattr(self, key)
            if current_val != default_val:
                result[key] = current_val
        return result


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