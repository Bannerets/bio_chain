import os
import telegram
import time
import re
import requests
import json
import html


CHAT_ID = -1001113029151
DB_FILENAME = 'users.json'
LAST_CHAIN_FILENAME = 'last_chain.txt'
r_scrape_bio = re.compile(r'<meta +property="og:description" +content="(.+?)".*>')
r_username = re.compile(r'@([a-zA-Z][\w\d]{4,31})')


class User(object):
    """
    State machine for each user that keeps track if the username/link_username has changed
    """
    def __init__(self, user_id, data=None):
        self.id = user_id
        self.expires = 0
        self.has_changed = False

        self.username = ''
        self.link_id = '0'
        self.link_username = ''

        if data:
            if 'username' in data: self.username = data['username']
            if 'link_id' in data: self.link_id = data['link_id']
            if 'link_username' in data: self.link_username = data['link_username']

    def is_expired(self):
        return time.time() > self.expires

    def reset_expiry(self, seconds=60):
        self.expires = time.time() + seconds

    def update_data(self, username, link_username, link_id):
        username = '' if not username else username
        link_username = '' if not link_username else link_username
        # allows detection of changing to an invalid link:
        # since this results from being unable to resolve link_username, this is the previous link_id
        link_id = link_id if link_id else self.link_id

        if username.lower() != self.username.lower():
            self.has_changed = True
            print(f'{self.username} -> {username}')
        if link_username.lower() != self.link_username.lower():
            self.has_changed = True
            print(f'{self.username} link: {self.link_username} -> {link_username}')
        if link_id != self.link_id:
            self.has_changed = True
            print(f'{self.username} link_id: {self.link_id} -> {link_id}')

        self.username = username
        self.link_username = link_username
        self.link_id = link_id



# dumps the important data to the json file
def save_db(db):
    db_dict = {}

    for user_id, user in db.items():
        db_dict[user_id] = {
            'username': user.username,
            'link_id': user.link_id,
            'link_username': user.link_username
        }

    with open(DB_FILENAME, 'w') as f:
        json.dump(db_dict, f)


# scrapes bio from t.me
def get_bio(username):
    #if username.lower() == 'katewastaken':
    #    return '@blonami'

    r = requests.get(f'http://t.me/{username}')
    if not r.ok:
        print(f'Request for @{username}\'s bio failed')
        return None

    bio = r_scrape_bio.findall(r.text)
    if not bio: return ''
    return html.unescape(bio[0])


# attempts to get the id of a user from their username by checking the db
def resolve_username(db, username):
    for this_id, this_user in db.items():
        if username.lower() == this_user.username.lower():
            return this_id, this_user.username
    return None, username


# gets new data for a user and updates the db
def update_user(bot, db, user_id):
    user_id = str(user_id)

    # get the user so we have an up-to-date username for this id
    try:
        user = bot.getChatMember(CHAT_ID, user_id).user
    except Exception as e:
        print('USER NOT IN GROUP???', e)
        return

    if user_id not in db:
        db[user_id] = User(user_id)
        print(f'added {user_id} to the db')

    # ignore bots
    if user.is_bot:
        return

    # if no username, watch this person
    if not hasattr(user, 'username'):
        db[user_id].reset_expiry(10)
        print(f'{user.first_name} has no username!')
        return

    # find first valid (in the db) username link
    links = r_username.findall(get_bio(user.username))
    link_id = None
    link_username = None
    for link in links:
        link_id, link_username = resolve_username(db, link)
        if link_id:
            break

    db[user_id].update_data(user.username, link_username, link_id)

    # if no links, watch this person
    if not link_id and user_id != '51863899':
        print(f'{user.first_name} has no valid links!')
        db[user_id].reset_expiry(10)
    else:
        db[user_id].reset_expiry(60)


# returns the user_id's associated with an update in the chat
def get_update_user_ids(update):
    ids = []
    if update.message and update.message.chat.id == CHAT_ID:
        for user in update.message.new_chat_members:
            if not user.is_bot: ids.append(user.id)
        user = update.message.from_user
        if not user.is_bot: ids.append(user.id)

    return ids

def send_message(bot, text):
    print('out:', text)
    return bot.sendMessage(
        chat_id=CHAT_ID,
        text=text,
        parse_mode='Markdown',
    )

def rebuild_chain(bot, db, trigger_id):
    trigger = db[trigger_id]
    linker_ids = []

    # find everyone who links to the trigger by id
    for user_id, user in db.items():
        if user.link_id == trigger_id:
            linker_ids.append(user_id)

    # verify that everyone who points to the trigger points to the currect username
    for linker_id in linker_ids:
        if db[linker_id].link_username.lower() != trigger.username.lower():
            if trigger.username:
                message = '@{} has changed their username to {}, @{} needs to update their bio'.format(
                    db[linker_id].link_username,
                    '@'+trigger.username if trigger.username else 'nothing',
                    db[linker_id].username
                )
                send_message(bot, message)


    # verify that trigger links to a valid username (only if they previously had a valid link!)
    # if not, then inform them and whoever links to them
    if trigger.link_id in db and db[trigger.link_id].username.lower() != trigger.link_username.lower():
        message = '@{} has an invalid link to {} (previously: @{})'.format(
            trigger.username,
            '@'+trigger.link_username if trigger.link_username else 'no one',
            db[trigger.link_id].username
        )
        for linker_id in linker_ids:
            message += '\n@{} points to @{} and should update their bio because of this!\n'.format(
                db[linker_id].username,
                trigger.username
            )
        send_message(bot, message)

    # find the head that results in the best chain
    best_length = 0
    best_chain = []
    for head_id, head in db.items():
        this_chain = [head_id]
        while this_chain[-1] in db:
            this_chain.append(db[this_chain[-1]].link_id)

        if len(this_chain) > best_length:
            best_chain = this_chain
            best_length = len(this_chain)

    chain_output = '```\nChain length: {}\n\n'.format(len(best_chain))
    for user_id in best_chain:
        chain_output += db[user_id].username
        link_id = db[user_id].link_id

        if link_id not in db:
            break

        if db[user_id].link_username.lower() == db[link_id].username.lower():
            chain_output += ' → '
        else:
            chain_output += ' ↛ '

    return chain_output + '```'



def main():
    with open(DB_FILENAME) as f:
        db = json.load(f)
    for user_id, data in db.items():
        db[user_id] = User(user_id, data)

    with open(LAST_CHAIN_FILENAME) as f:
        last_chain = f.read()

    bot = telegram.Bot(os.environ['tg_bot_biochain_token'])

    next_update_id = -1
    while 1:
        for user_id, user in db.items():
            if user.is_expired():
                update_user(bot, db, user_id)

        updates = bot.getUpdates(offset=next_update_id)
        for update in updates:
            for user_id in get_update_user_ids(update):
                if str(user_id) not in db:
                    update_user(bot, db, user_id)
            next_update_id = update.update_id + 1

        this_chain = rebuild_chain(bot, db, '51863899')
        for user_id, user in db.items():
            if user.has_changed:
                this_chain = rebuild_chain(bot, db, user_id)
                user.has_changed = False
                save_db(db)

        if this_chain and this_chain.lower() != last_chain.lower():
            message = send_message(bot, this_chain)
            if message:
                bot.pinChatMessage(
                    chat_id=CHAT_ID,
                    message_id=message.message_id,
                    disable_notification=True
                )
            with open(LAST_CHAIN_FILENAME, 'w') as f:
                f.write(this_chain)
            last_chain = this_chain

        time.sleep(1)

if __name__ == '__main__':
    main()