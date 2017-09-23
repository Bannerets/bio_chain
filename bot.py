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




# link matrix
def load_links(link_matrix):
    """Updates link_matrix in place with the entries from LINKS_FILENAME"""
    with open(LINKS_FILENAME) as f:
        data = json.load(f)

    for user_id, links in data.items():
        for link in links:
            link_matrix[user_id][link] = State.Old


def save_links(link_matrix):
    """Dumps link_matrix to LINKS_FILENAME"""
    out = defaultdict(list)

    for user_id in link_matrix:
        for link_id in link_matrix[user_id]:
            if link_matrix[user_id][link_id] is not State.Empty:
                out[user_id].append(link_id)

    with open(LINKS_FILENAME, 'w') as f:
        json.dump(out, f)


def print_matrix(link_matrix, userdb):
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

def is_userid_in_group(bot, user_id):
    try:
        member = bot.getChatMember(CHAT_ID, user_id)
        if member:
            return True
    except Exception as e:
        if 'User_id_invalid' in e.message:
            print(f'{user_id} is not in the group!')
            return False
    return True




def is_chain_valid(chain, link_matrix):
    """Returns True if all the links in the chain are valid"""
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is not State.Current:
            return False

    return True

def chain_count_valid(chain, link_matrix):
    valid = 0
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is State.Current:
            valid += 1

    return valid


def find_best_chain(link_matrix, userdb):
    """
    Returns a tuple:
    [0] = the best possible chain (most valid links) from link_matrix
    [2] = True if the longest chain is valid
    """
    best_chain = []
    best_chain_valid = -1

    pending_chains = []

    # add every possible head to pending_chains
    for head_id in link_matrix:
        pending_chains.append([head_id])

    while pending_chains:
        # grab a chain from the stack
        this_chain = pending_chains.pop()
        last_link = this_chain[-1]

        # iterate through all the links that the last_link in this_chain links to
        for next_link in link_matrix[last_link]:
            # if next_link is valid and we have not visited it before
            if link_matrix[last_link][next_link] is not State.Empty and next_link not in this_chain:
                # add [this_chain + next_link] to pending_chains
                new_chain = this_chain[:]
                new_chain.append(next_link)
                pending_chains.append(new_chain)

        # if last_link is the end, then test if this is the longest/best chain
        if last_link == '51863899':
            this_valid = chain_count_valid(this_chain, link_matrix)
            if this_valid > best_chain_valid:
                best_chain_valid = this_valid
                best_chain = this_chain

    print('', stringify_chain_short(best_chain, link_matrix, userdb))
    return best_chain, is_chain_valid(best_chain, link_matrix)


def get_links_to(link_matrix, user_id):
    """Returns a list of user_ids that currently link to user_id"""
    return [link_id for link_id in link_matrix if link_matrix[link_id][user_id] is State.Current]


def stringify_chain(chain, link_matrix, userdb):
    """Converts a chain into a string"""
    chain_str = f'Chain length: {len(chain)}\n\n'
    
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        chain_str += f'@{userdb[this_id].username}'
        chain_str += ' → ' if link_matrix[this_id][next_id] is State.Current else ' ❌ '

    chain_str += f'@{userdb[chain[-1]].username}'

    return chain_str


def stringify_chain_short(chain, link_matrix, userdb):
    """Converts a chain into a shorter debug string than stringify_chain"""
    def short_name(name):
        nonlocal names
        end = 3
        while name[:end] in names and end <= len(name):
            end += 1
        names.add(name[:end])
        return name[:end]

    chain_str = f'({len(chain)}) '
    names = set()
    
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        chain_str += '@{}'.format(short_name(userdb[this_id].username))
        chain_str += ' → ' if link_matrix[this_id][next_id] is State.Current else ' ❌ '

    chain_str += '@{}'.format(short_name(userdb[chain[-1]].username))

    return chain_str




def user_has_valid_link(user_id, link_matrix):
    for link_id in link_matrix[user_id]:
        if link_matrix[user_id][link_id] is State.Current:
            return True
    return False

def get_chain_announcements(chain, link_matrix, userdb):
    """Returns a list of any announcements that need to be made because of broken links in a chain"""
    announcements = []

    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is not State.Current:
            announcements.append(f'@{userdb[this_id].username} has no valid links (should be `@{userdb[next_id].username}`)!')
            for link_id in get_links_to(link_matrix, this_id):
                announcements.append(f'@{userdb[link_id].username} should update their bio because of this!')

    for user_id in userdb:
        if user_id not in chain and user_has_valid_link(user_id, link_matrix):
            announcements.append(f'Suggestion: @{userdb[user_id].username} should link to `@{userdb[chain[0]].username}`!')

    return announcements


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

    # get last message that we sent
    with open(LAST_PIN_FILENAME) as f:
        last_pin_id = f.read()

    try:
        # try to edit our last pinned message
        message = bot.editMessageText(
            chat_id=CHAT_ID,
            message_id=last_pin_id,
            text=chain_text
        )  
    except:
        # can't edit? send a new one (in monospace to prevent notifications)
        message = send_message(bot, f'```\n{chain_text}```')
        if message:
            bot.editMessageText(
                chat_id=CHAT_ID,
                message_id=message.message_id,
                text=chain_text
            )
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
            # don't reset the expiry time of the users
            print('Handling updates...')
            has_changed = False
            updates = bot.getUpdates(offset=next_update_id)
            for update in updates:
                for user_id, username in get_update_users(update):
                    if userdb[user_id].update_username(username, reset=False):
                        has_changed = True
                #next_update_id = update.update_id + 1



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


            #print_matrix(link_matrix, userdb)


            # find the best chain and check if it passes through only real links
            has_changed = False
            best_chain, all_valid = find_best_chain(link_matrix, userdb)
            best_chain_str = stringify_chain(best_chain, link_matrix, userdb)
            if update_chain(bot, best_chain_str):
                print('Chain has been updated!' + (' and is now in an optimal state!' if all_valid else ''))
                has_changed = True
                for announcement in get_chain_announcements(best_chain, link_matrix, userdb):
                    send_message(bot, announcement)



            # Get rid of old non-existent links if the chain passes through only real links
            purge_count = 0
            if all_valid:
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




            # Get rid of users who are not in the group
            if all_valid:
                best_chain = set(best_chain)
                new_db = defaultdict(lambda: User(''))
                for user_id in userdb:
                    if user_id in best_chain or is_userid_in_group(bot, user_id):
                        new_db[user_id] = userdb[user_id]

                purge_count = len(userdb) - len(new_db)
                if purge_count:
                    userdb = new_db
                    print(f'Purged {purge_count} non-group members(s)! Saving userdb...')
                    save_userdb(userdb)



            time.sleep(60)
        except Exception as e:
            print('Encountered exception while running main loop:', e)
            raise e


if __name__ == '__main__':
    main()