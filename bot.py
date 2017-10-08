import os
import telegram
import time
import json
from shutil import copyfile
import traceback

import matrix
import chain
import changes
from util import *

DATABASE_FILENAME = 'db.json'
LAST_CHAIN_FILENAME = 'last_chain.txt'
LAST_PIN_FILENAME = 'last_pin.txt'


def update_chain(bot, chain_text):
    """
    Tries to post chain_text (editing the last message if possible)
    Returns True if chain_text was sent, False if not
    """
    # get last chain
    with open(LAST_CHAIN_FILENAME) as f:
        last_chain = f.read()

    if chain_text == last_chain:
        return False

    # get last message that we sent
    with open(LAST_PIN_FILENAME) as f:
        last_pin_id = f.read()

    if len(chain_text) >= 3000:
        send_message(bot, '@KateWasTaken Warning: The chain is approaching message character limit ({:.1%})'.format(
            len(chain_text) / 4096
        ))

    try:
        # try to edit our last pinned message
        message = bot.editMessageText(
            chat_id=CHAT_ID,
            message_id=last_pin_id,
            text=chain_text
        )
    except:
        # can't edit? send a placeholder and then edit it to prevent notifications
        message = send_message(bot, 'the game')
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

    with open(LAST_CHAIN_FILENAME, 'w') as f:
        f.write(chain_text)

    return True



def get_update_users(update):#td check if can return from generator
    """Yields the user IDs and usernames associated with an update in the chat"""
    if update.message and update.message.chat.id == CHAT_ID:
        for user in update.message.new_chat_members:
            if not user.is_bot:
                yield str(user.id), user.username or ''
        user = update.message.from_user
        if not user.is_bot:
            yield str(user.id), user.username or ''



def save_db(db, backup=True):
    """Backs up the current file and then dumps db to DATABASE_FILENAME"""
    print('Saving db...' + ('' if backup else '(no backup)'))

    if backup:
        copyfile(DATABASE_FILENAME, 'bk/db{}.json'.format(current_timestamp()))

    with open(DATABASE_FILENAME, 'w') as f:
        json.dump(db, f)


def main():
    with open(DATABASE_FILENAME) as f:
        db = json.load(f)

    link_matrix = matrix.from_db(db)
    
    bot = telegram.Bot(os.environ['tg_bot_biochain_token'])
    next_update_id = -100

    # user ids that we failed to update a username for
    needs_verification = []
    # people that we might need to shout at if they caused a break in the chain
    pending_changes = []
    while 1:
        try:
            # Add users who are not in the db to the db
            #print('Handling updates...')
            has_changed = False
            try:
                updates = bot.getUpdates(offset=next_update_id)
            except telegram.error.TimedOut:
                updates = []
            for update in updates:
                for user_id, username in get_update_users(update):
                    if user_id not in db:
                        print(f'Adding @{username} ({user_id}) to the db...')
                        db[user_id] = {'username': username}
                        has_changed = True
                    elif db[user_id].get('disabled', False):
                        print(f'Enabling previously disabled user: @{username} ({user_id})...')
                        db[user_id]['username'] = username
                        db[user_id]['disabled'] = False
                next_update_id = update.update_id + 1

            if has_changed:
                save_db(db)



            # find the user who expires next
            expired_count = 0
            expired_id = None
            min_timestamp = -1
            for user_id in db:
                this_expires = db[user_id].get('expires', 0)
                if not db[user_id].get('disabled', False):
                    if this_expires < current_timestamp():
                        expired_count += 1
                    if not expired_id or this_expires <= db[expired_id].get('expires', 0):
                        expired_id = user_id
                        min_timestamp = this_expires

            # if the user who expires next isn't expired, dont do anything
            if min_timestamp > current_timestamp():
                print('we have {} seconds until the next user expires!'.format(
                    min_timestamp - current_timestamp()
                ))
                time.sleep(1)
                continue
            if expired_count > 1:
                print(f'Warning: there are {expired_count} users that need updating!')

            last_username = db[expired_id]['username']
            print('[{}]: now updating: {} ({}) T-{}'.format(
                current_timestamp(), last_username, expired_id, current_timestamp() - min_timestamp
            ))


            # update the username of this user
            has_changed = False
            try:
                username = get_username_from_id(bot, expired_id)
                if username != last_username:
                    pending_changes.append( changes.Username(expired_id, last_username, username) )
                    has_changed = True
                    db[expired_id]['username'] = username
            except Exception as e:
                if 'timed out' in e.message.lower():
                    print('oh man oh geez that didnt work')
                    continue
                needs_verification.append(expired_id)

            # if the username has changed, mark everyone who points to this person as needing an update
            if has_changed:
                for user_id in matrix.get_links_from(link_matrix, expired_id):
                    print('un: Marking {} ({}) for updating!'.format(
                        db[user_id]['username'],
                        user_id
                    ))
                    db[user_id]['expires'] = 0
                save_db(db)


            # Fetch the users that this person links to in their bio
            current_links_to = get_usernames_from_bio(db, expired_id)
            last_links_to = set(db[expired_id].get('bio', []))

            # if their bio has changed
            if current_links_to != last_links_to:
                # we might need to shout at them
                pending_changes.append( changes.Bio(expired_id, last_links_to, current_links_to) )

                db[expired_id]['bio'] = list(current_links_to)
                # Mark everyone who this person linked to as needing an update
                for user_id in matrix.get_links_to(link_matrix, expired_id):
                    print('bio: Marked "{}" ({}) for updating!'.format(
                        db[user_id]['username'],
                        user_id
                    ))
                    db[user_id]['expires'] = 0


            db[expired_id]['expires'] = current_timestamp() + 60

            expired_count = 0
            for user_id in db:
                this_expires = db[user_id].get('expires', 0)
                if not db[user_id].get('disabled', False) and this_expires < current_timestamp():
                        expired_count += 1

            if expired_count or not pending_changes:
                continue





            # build a translation table from db: username -> user_id
            username_to_id = {}
            for user_id, user in db.items():
                if user.get('disabled', False):
                    continue
                username_to_id[user['username'].lower()] = user_id

            # Make all links old, so that changes can be caught
            for user_id in link_matrix:
                for link_id in matrix.get_links_from(link_matrix, user_id):
                    link_matrix[user_id][link_id] = matrix.State.Old

            # update the matrix with the bio data (using the translation table)
            for user_id, user in db.items():
                for link_username in user.get('bio', []):
                    link_id = username_to_id.get(link_username.lower(), 0)
                    if link_id:
                        link_matrix[link_id][user_id] = matrix.State.Current

            if matrix.update_db(link_matrix, db):
                save_db(db)



            # find the best chain and post it if it's different to our old one
            print('Finding best chain...')
            best_chain, branches, best_is_valid = chain.find_best(link_matrix, db)
            if update_chain(bot, chain.stringify(best_chain, link_matrix, db)):
                print('Chain has been updated!' + (' and is now in an optimal state!' if best_is_valid else ''))
                send_message(bot, chain.get_branch_announcements(best_chain, branches, link_matrix, db))


            for shout in pending_changes:
                send_message(bot, shout.shout(link_matrix, db, best_chain, username_to_id))
            pending_changes.clear()

            # disable users who are not reachable and not in the group
            print('Finding detached nodes...')
            #reachable_nodes = chain.flood_fill(link_matrix) #td:figure out why i thought i needed this
            has_changed = False
            for user_id in needs_verification:
                if (not db[user_id].get('disabled', False) and user_id not in best_chain):
                    print('Disabling id:{}...'.format(user_id))
                    has_changed = True
                    db[user_id]['disabled'] = True
            needs_verification.clear()

            # Give users in the main chain a timestamp if they have none
            for user_id in best_chain:
                if 'joined' not in db[user_id]:
                    db[user_id]['joined'] = current_timestamp()
                    has_changed = True

            if has_changed:
                save_db(db)



            if not best_is_valid:
                continue

            # Get rid of old non-existent links if the chain passes through only real links
            change_count = 0
            if best_is_valid:
                for user_id in link_matrix:
                    for link_id in matrix.get_links_from(link_matrix, user_id, lambda link: link is matrix.State.Old):
                        link_matrix[user_id][link_id] = matrix.State.Empty
                        change_count += 1
                if change_count:
                    print(f'Purged {change_count} old links!')

            if matrix.update_db(link_matrix, db):
                save_db(db)
        except Exception as e:
            print('Encountered exception while running main loop:', e)
            send_message(bot, '```\n{}\n{}```'.format(type(e), traceback.format_exc()), 232787997)
            #raise e

if __name__ == '__main__':
    main()
