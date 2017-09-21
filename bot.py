import os
import telegram
import time
import re
import requests
import json
import html
from collections import defaultdict
from enum import Enum


CHAT_ID = -1001113029151
LINKS_FILENAME = 'links.json'
USERDB_FILENAME = 'users.json'
LAST_CHAIN_FILENAME = 'last_chain.txt'
LAST_PIN_FILENAME = 'last_pin.txt'
re_scrape_bio = re.compile(r'<meta +property="og:description" +content="(.+?)".*>')
re_username = re.compile(r'@([a-zA-Z][\w\d]{4,31})')


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
            if self.username:
                print(f'{self.username} -> {username}')
            self.username = username
            return True
        return False


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




def load_links(link_matrix):
    """Updates link_matrix in place with the entries from LINKS_FILENAME"""
    with open(LINKS_FILENAME) as f:
        data = json.load(f)

    for user_id, links in data.items():
        for link in links:
            link_matrix[user_id][link] = State.Old


def save_links(link_matrix):
    """Dumps link_matrix to LINKS_FILENAME"""
    out = {}

    for user_id in link_matrix:
        out[user_id] = []
        for link_id in link_matrix[user_id]:
            if link_matrix[user_id][link_id] is not State.Empty:
                out[user_id].append(link_id)

    with open(LINKS_FILENAME, 'w') as f:
        json.dump(out, f)


def print_matrix(link_matrix):
    """Prints link_matrix in a grid"""
    print(' ' * 13, end='')
    i = 0
    for key in link_matrix:
        print('{0: >2} '.format(chr(i + 65)), end='')
        i += 1
    print()


    i = 0
    for basekey in link_matrix:
        print('{} {}'.format(chr(i + 65), basekey).ljust(12) + ':', end='')
        for key in link_matrix:
            print('{0: >2} '.format(link_matrix[basekey][key].value), end='')
        print()
        i += 1




def load_userdb(userdb):
    """Updates user database with data from USERDB_FILENAME"""
    with open(USERDB_FILENAME) as f:
        data = json.load(f)

    for user_id, username in data.items():
        userdb[user_id].update_username(username, reset=False)


def save_userdb(data):
    """Dumps the user database to USERDB_FILENAME as JSON"""
    out = {user_id: user.username for user_id, user in data.items()}

    with open(USERDB_FILENAME, 'w') as f:
        json.dump(out, f)




def get_id_from_username(userdb, username):
    """
    Attemps to get the ID for the given username by checking in the userdb.
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
    if not username: return []

    r = requests.get(f'http://t.me/{username}')
    if not r.ok:
        print(f"Request for @{username}'s bio failed")
        return []

    bio = re_scrape_bio.findall(r.text)
    if not bio:
        return []
    bio = html.unescape(bio[0])
    link_names = re_username.findall(bio)
    
    link_ids = []
    for link_name in link_names:
        link_id = get_id_from_username(userdb, link_name)
        if link_id:
            link_ids.append(link_id)

    return link_ids


def get_username(bot, user_id):
    """Returns the username of the user_is, may return None if the user has never contacted the bot"""
    try:
        chat = bot.getChat(user_id)
        return chat.username if hasattr(chat, 'username') else ''
    except Exception as e:
        print(f'I don\'t know who {user_id} is:', e)

    return None




def find_longest_chain(link_matrix):
    """Returns the longest possible chain from link_matrix"""
    longest_chain = []
    pending_chains = []

    # add every possible head to pending_chains
    for head_id in link_matrix:
        pending_chains.append([head_id])

    while pending_chains:
        # grab a chain from the stack
        this_chain = pending_chains.pop()
        last_link = this_chain[-1]

        # if the last_link doesn't have any links then this will remain True
        is_end = True

        # iterate through all the links that the last_link in this_chain links to
        for next_link in link_matrix[last_link]:
            # if next_link is valid and we have not visted it before
            if link_matrix[last_link][next_link] is not State.Empty and next_link not in this_chain:
                # last_link is not the end of a chain
                is_end = False

                # add [this_chain + next_link] to pending_chains
                new_chain = this_chain[:]
                new_chain.append(next_link)
                pending_chains.append(new_chain)

        # if last_link is the end, then test if this is the longest chain
        if is_end and len(this_chain) > len(longest_chain):
                longest_chain = this_chain

    return longest_chain


def get_links_to(link_matrix, user_id):
    """Returns a list of user_ids that currently link to user_id"""
    return [link_id for link_id in link_matrix if link_matrix[link_id][user_id] is State.Current]


def verify_chain(chain, link_matrix, userdb):
    """
    Converts the chain into a printable string and verifies that all the links are valid
    Returns a tuple: the chain as a string, a list of any announcements that need to be made, True if all the links are valid
    """
    announcements = []
    chain_str = '```\nChain length: {}\n\n'.format(len(chain))

    all_valid = True
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        chain_str += f'@{userdb[this_id].username}'
        if link_matrix[this_id][next_id] is State.Current:
            chain_str += ' → '
        else:
            all_valid = False
            chain_str += ' ❌ '
            announcements.append(f'@{userdb[this_id].username} has no valid links (should be @{userdb[next_id].username})!')
            for link_id in get_links_to(link_matrix, this_id):
                announcements.append(f'@{userdb[link_id].username} should update their bio because of this!')

    chain_str += f'@{userdb[chain[-1]].username}```'

    return chain_str, announcements, all_valid


def update_chain(bot, chain_text):
    """
    Tries to post chain_text (editing the last message if possible)
    Returns True if chain_text was sent, False if not
    """
    # get last chain
    with open(LAST_CHAIN_FILENAME) as f:
        last_chain = f.read()
    if last_chain == chain_text:
        return False

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

    return True




def send_message(bot, text):
    """Prints a message and then sends it via the bot to the chat"""
    print('out:', text)
    return bot.sendMessage(
        chat_id=CHAT_ID,
        text=text,
        parse_mode='Markdown',
    )


def get_update_users(update):
    """Yields the user IDs and usernames associated with an update in the chat"""
    if update.message and update.message.chat.id == CHAT_ID:
        for user in update.message.new_chat_members:
            if not user.is_bot:
                yield str(user.id), user.username if hasattr(user, 'username') else ''
        user = update.message.from_user
        if not user.is_bot:
            yield str(user.id), user.username if hasattr(user, 'username') else ''


def main():
    link_matrix = defaultdict(
        lambda: defaultdict(
            lambda: State.Empty
        )
    )
    load_links(link_matrix)

    userdb = defaultdict(lambda: User(''))
    load_userdb(userdb)

    bot = telegram.Bot(os.environ['tg_bot_biochain_token'])
    next_update_id = -100

    while 1:
        try:
            # update userdb from bot updates (adding users who aren't in the db)
            # dont reset the expiry time of the users
            print('Handling updates...')
            has_changed = False
            updates = bot.getUpdates(offset=next_update_id)
            for update in updates:
                for user_id, username in get_update_users(update):
                    if userdb[user_id].update_username(username, reset=False):
                        has_changed = True
                next_update_id = update.update_id + 1



            # update the usernames of the users who are marked as expired
            print('Updating usernames...')
            for user_id, user in userdb.items():
                if user.is_expired():
                    if user.update_username(get_username(bot, user_id)):
                        has_changed = True

            if has_changed:
                print('Saving userdb...')
                save_userdb(userdb)



            # Update the link_matrix of all users in the db based on their bios
            print('Scraping bios...')
            for user_id in userdb:
                for link_id in get_link_ids_from_bio(userdb, userdb[user_id].username):
                    link_matrix[user_id][link_id] = State.Current



            # find the best chain and check if it passes through only real links
            has_changed = False
            new_chain = find_longest_chain(link_matrix)
            new_chain_str, announcements, all_valid = verify_chain(new_chain, link_matrix, userdb)
            if update_chain(bot, new_chain_str):
                print('Chain has been updated!' + (' and is now in an optimal state!' if all_valid else ''))
                has_changed = True
                for announcement in announcements:
                    send_message(bot, announcement)



            # Get rid of old non-existent links if the chain passes through only real links
            if all_valid:
                purge_count = 0
                for linker_id in link_matrix:
                    for link_id in link_matrix:
                        if link_matrix[linker_id][link_id] is State.Old:
                            link_matrix[linker_id][link_id] = State.Empty
                            purge_count += 1
                if purge_count:
                    print(f'Purged {purge_count} old links!')

            if has_changed or purge_count:
                print('Saving link matrix...')
                save_links(link_matrix)

            # Get rid of users who do not appear in the chain
            if all_valid:
                purge_count = len(userdb)
                new_chain = set(new_chain)
                userdb = {user_id: user for user_id, user in userdb.items() if user_id in new_chain}
                purge_count -= len(userdb)
                if purge_count:
                    print(f'Purged {purge_count} old users! Saving userdb...')
                    save_userdb(userdb)


            time.sleep(60)

        except Exception as e:
            print('Encountered exception while running main loop:', e)
            raise e



if __name__ == '__main__':
    main()
