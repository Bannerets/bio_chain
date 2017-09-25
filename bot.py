import os
import telegram
import time
import json
from shutil import copyfile

import matrix
import chain
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
    if last_chain == chain_text:
        return False

    # get last message that we sent
    with open(LAST_PIN_FILENAME) as f:
        last_pin_id = f.read()

    if len(chain_text) >= 3000:
        send_message(bot, '@KateWasTaken Warning: The chain is approaching message character limit ({:.1%}%)'.format(
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



def get_update_users(update):
    """Yields the user IDs and usernames associated with an update in the chat"""
    if update.message and update.message.chat.id == CHAT_ID:
        for user in update.message.new_chat_members:
            if not user.is_bot:
                yield str(user.id), user.username if hasattr(user, 'username') else ''
        user = update.message.from_user
        if not user.is_bot:
            yield str(user.id), user.username if hasattr(user, 'username') else ''



def save_db(db):
    """Backs up the current file and then dumps db to DATABASE_FILENAME"""
    print('Saving db...')

    copyfile(DATABASE_FILENAME, 'db{}.json'.format(int(time.time())))

    with open(DATABASE_FILENAME, 'w') as f:
        json.dump(db, f)



def main():
    with open(DATABASE_FILENAME) as f:
        db = json.load(f)

    link_matrix = matrix.from_db(db)

    bot = telegram.Bot(os.environ['tg_bot_biochain_token'])
    next_update_id = -100


    while 1:
        try:
            # Add users who are not in the db to the db
            print('Handling updates...')
            has_changed = False
            updates = bot.getUpdates(offset=next_update_id)
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



            # update the usernames of the user in the db
            print('Updating usernames...')
            for user_id in db:
                if db[user_id].get('disabled', False): continue

                username = get_userid_username(bot, user_id)
                if username != db[user_id]['username']:
                    print('"{}" -> "{}" ({})'.format(
                        db[user_id]['username'], username, user_id
                    ))
                    has_changed = True
                    if username:
                        db[user_id]['username'] = username

            if has_changed:
                save_db(db)


            # Update the link_matrix of all users in the db based on their bios
            print('Scraping bios...')
            for user_id in db:
                if db[user_id].get('disabled', False): continue
                for link_id in get_userids_from_bio(db, db[user_id]['username']):
                    link_matrix[link_id][user_id] = matrix.State.Current

            if matrix.update_db(link_matrix, db):
                save_db(db)



            # find the best chain and post it if it's different to our old one
            print('Finding best chain...')
            best_chain, chains, best_is_valid = chain.find_best(link_matrix, db)
            best_chain_str = chain.stringify(best_chain, link_matrix, db)
            if update_chain(bot, best_chain_str):
                print('Chain has been updated!' + (' and is now in an optimal state!' if best_is_valid else ''))
                send_message(bot, '\n'.join(
                    chain.get_announcements(best_chain, chains, link_matrix, db)
                ))


            # disable users who are not reachable and not in the group
            reachable_nodes = chain.flood_fill(link_matrix)
            change_count = 0
            for user_id in db:
                if (not db[user_id].get('disabled', False)
                    and user_id not in reachable_nodes
                    and not is_userid_in_group(bot, user_id)
                ):
                    print('Disabling @{}...'.format(db[user_id]['username']))
                    change_count += 1
                    db[user_id]['disabled'] = True


            # Give users in the main chain a timestamp if they have none
            for user_id in best_chain:
                if 'joined' not in db[user_id]:
                    db[user_id]['joined'] = int(time.time())
                    change_count += 1

            if change_count:
                save_db(db)



            # Get rid of old non-existent links if the chain passes through only real links
            change_count = 0
            if best_is_valid:
                for user_id in link_matrix:
                    for link_id in link_matrix[user_id]:
                        if link_matrix[user_id][link_id] is matrix.State.Old:
                            link_matrix[user_id][link_id] = matrix.State.Empty
                            change_count += 1
                if change_count:
                    print(f'Purged {change_count} old links!')


            # Make all links old, so that changes can be caught
            for user_id in link_matrix:
                for link_id in link_matrix[user_id]:
                    if link_matrix[user_id][link_id] is matrix.State.Current:
                        link_matrix[user_id][link_id] = matrix.State.Old
                        change_count += 1



            if matrix.update_db(link_matrix, db):
                save_db(db)
            #exit()

            time.sleep(60)
        except Exception as e:
            print('Encountered exception while running main loop:', e)
            #raise e

if __name__ == '__main__':
    main()