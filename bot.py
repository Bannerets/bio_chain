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
LAST_PIN_FILENAME = 'last_pin.txt'
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

        data = data if data else {}
        self.username = data.get('username', '')
        self.link_id = data.get('link_id', '0')
        self.link_username = data.get('link_username', '')

    def is_expired(self):
        return time.time() > self.expires

    def reset_expiry(self, seconds=60):
        self.expires = time.time() + seconds

    def update_data(self, username, link_username, link_id):
        username = username if username else ''
        link_username = link_username if link_username else ''
        # allows detection of changing to an invalid link:
        # since this results from being unable to resolve link_username,
        # this is the previous link_id
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


def save_db(db):
    """Dumps the most important data to DB_FILENAME as JSON"""
    db_dict = {}

    for user_id, user in db.items():
        db_dict[user_id] = {
            'username': user.username,
            'link_id': user.link_id,
            'link_username': user.link_username
        }

    with open(DB_FILENAME, 'w') as f:
        json.dump(db_dict, f)


def get_bio(username):
    """Scrapes the bio from t.me/username"""
    r = requests.get(f'http://t.me/{username}')
    if not r.ok:
        print(f"Request for @{username}'s bio failed")
        return ''

    bio = r_scrape_bio.findall(r.text)
    return html.unescape(bio[0]) if bio else ''


def resolve_username(db, username):
    """
    Attemps to get the ID for the given username by checking in the db.
    Returns a tuple of (id, username), where id may be None if not found.
    """
    for this_id, this_user in db.items():
        if username.lower() == this_user.username.lower():
            return this_id



def update_user(bot, db, user_id):
    """gets new data for a user and updates the db"""
    user_id = str(user_id)

    # get the user so we have an up-to-date username for this id
    username = resolve_username(db, user_id)
    try:
        chat = bot.getChat(user_id)
        if hasattr(chat, 'username'):
            username = chat.username
    except Exception as e:
        print('USER NOT IN GROUP???', user_id, e)

    if user_id not in db:
        db[user_id] = User(user_id)
        print(f'added {user_id} to the db')

    # if no username, watch this person
    if not username:
        db[user_id].reset_expiry(10)
        print(f'{user_id} has no username!')
        return

    # find first valid (in the db) username link
    links = r_username.findall(get_bio(username))
    link_id = None
    link_username = links[-1] if links else ''
    for link in links:
        link_id = resolve_username(db, link)
        if link_id:
            link_username = link
            break

    if link_username.lower() == username.lower():
        link_username = 'self'
        link_id = None

    db[user_id].update_data(username, link_username, link_id)

    # if no links, watch this person
    if not link_id and user_id != '51863899':
        print(f'{username} has no valid links!')
        db[user_id].reset_expiry(10)
    else:
        db[user_id].reset_expiry(60)


def get_update_user_ids(update):
    """Returns the user IDs associated with an update in the chat"""
    ids = []
    if update.message and update.message.chat.id == CHAT_ID:
        for user in update.message.new_chat_members:
            if not user.is_bot:
                ids.append(user.id)
        user = update.message.from_user
        if not user.is_bot:
            ids.append(user.id)

    return ids

def send_message(bot, text):
    print('out:', text)
    return bot.sendMessage(
        chat_id=CHAT_ID,
        text=text,
        parse_mode='Markdown',
    )

def verify_user(bot, db, trigger_id):
    trigger = db[trigger_id]
    linker_ids = []

    # find everyone who links to the trigger by id
    for user_id, user in db.items():
        if user.link_id == trigger_id:
            linker_ids.append(user_id)

    # verify that everyone who points to the
    # trigger points to the currect username
    for linker_id in linker_ids:
        if db[linker_id].link_username.lower() != trigger.username.lower():
            message = '@{} has changed their username to {}, @{} needs to update their bio.'.format(
                db[linker_id].link_username,
                '@'+trigger.username if trigger.username else 'nothing',
                db[linker_id].username
            )

            send_message(bot, message)

    # verify that trigger links to a valid username (only if they previously had a valid link!)
    # if not, then inform them and whoever links to them
    if trigger.link_id in db and \
            db[trigger.link_id].username.lower() != trigger.link_username.lower():
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

def rebuild_chain(db):
    # find the head that results in the longest chain
    best_length = 0
    best_chain = []
    for head_id, head in db.items():
        this_chain = [head_id]
        visited = set()
        while this_chain[-1] in db:
            visited.add(this_chain[-1])
            next_id = db[this_chain[-1]].link_id
            if next_id in visited:
                break
            this_chain.append(next_id)

        if len(this_chain) > best_length:
            best_chain = this_chain
            best_length = len(this_chain)

    # make a string from the chain list
    chain_output = '```\nChain length: {}\n\n'.format(len(best_chain)-1)
    for user_id in best_chain:
        chain_output += f'@{db[user_id].username}'
        link_id = db[user_id].link_id

        if link_id not in db:
            break

        if db[user_id].link_username.lower() == db[link_id].username.lower():
            chain_output += ' → '
        else:
            chain_output += ' ↛ '

    return chain_output + '```'

def send_chain(bot, chain_text):
    # get last message
    with open(LAST_PIN_FILENAME) as f:
        last_pin_id = f.read()

    try:
        bot.editMessageText(
            chat_id=CHAT_ID,
            message_id=last_pin_id,
            text=chain_text,
            parse_mode='Markdown'
        )
    except:
        message = send_message(bot, chain_text)
        if message:
            bot.pinChatMessage(
                chat_id=CHAT_ID,
                message_id=message.message_id,
                disable_notification=True
            )
            with open(LAST_PIN_FILENAME, 'w') as f:
                f.write(str(message.message_id))
    finally:
        with open(LAST_CHAIN_FILENAME, 'w') as f:
            f.write(chain_text)


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
        try:
            # update expired users
            for user_id, user in db.items():
                if user.is_expired():
                    update_user(bot, db, user_id)

            # find updates from users that we don't know, and add them to the db
            updates = bot.getUpdates(offset=next_update_id)
            for update in updates:
                for user_id in get_update_user_ids(update):
                    if str(user_id) not in db:
                        update_user(bot, db, user_id)
                next_update_id = update.update_id + 1

            # handle users that changed
            db_needs_save = False
            for user_id, user in db.items():
                if user.has_changed:
                    verify_user(bot, db, user_id)
                    user.has_changed = False
                    db_needs_save = True
            
            if db_needs_save:
                save_db(db)

            # rebuild the chain and send it if it's different from the previous one
            this_chain = rebuild_chain(db)
            if this_chain.lower() != last_chain.lower():
                send_chain(bot, this_chain)
                last_chain = this_chain

            time.sleep(1)
        except Exception as e:
            print("Encountered exception while running main loop:", e)

if __name__ == '__main__':
    main()
