import os
import telegram
import time
from collections import defaultdict

import userdb
import matrix
import chain

CHAT_ID = -1001113029151
LAST_CHAIN_FILENAME = 'last_chain.txt'
LAST_PIN_FILENAME = 'last_pin.txt'



def send_message(bot, text):
    """Prints a message and then sends it via the bot to the chat"""
    print('out:', text)
    return bot.sendMessage(
        chat_id=CHAT_ID,
        text=text,
        parse_mode='Markdown',
    )



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
        send_message(bot, '@KateWasTaken Warning: The chain is approaching message character limit ({:.1f}%)'.format(
            len(chain_text) / 40.96
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



def is_userid_in_group(bot, user_id):
    """Tests if a givedn user_id is in the group"""
    try:
        member = bot.getChatMember(CHAT_ID, user_id)
        if member:
            return True
    except Exception as e:
        if 'User_id_invalid' in e.message:
            print(f'{user_id} is not in the group!')
            return False
    return True



def id_to_username(bot, user_id):
    """Returns the username of the user_is, may return None if the user has never contacted the bot"""
    try:
        chat = bot.getChat(user_id)
        return chat.username if hasattr(chat, 'username') else ''
    except Exception as e:
        print(f'I don\'t know who {user_id} is:', e)

    return None



def main():
    link_matrix = matrix.load()
    users = userdb.load()


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
                    if users[user_id].update_username(username, reset=False):
                        has_changed = True



            # update the usernames of the users who are marked as expired
            print('Updating usernames...')
            for user_id, user in users.items():
                if user.is_expired():
                    if user.update_username(id_to_username(bot, user_id)):
                        has_changed = True

            if has_changed:
                print('Saving userdb...')
                userdb.save(users)



            # Update the link_matrix of all users in the db based on their bios
            print('Scraping bios...')
            for user_id in users:
                for link_id in userdb.get_link_ids_from_bio(users, users[user_id].username):
                    link_matrix[user_id][link_id] = matrix.State.Current



            # find the best chain and check if it passes through only real links
            has_changed = False
            best_chain, all_valid = chain.find_best(link_matrix, users)
            best_chain_str = chain.stringify(best_chain, link_matrix, users)
            if update_chain(bot, best_chain_str):
                print('Chain has been updated!' + (' and is now in an optimal state!' if all_valid else ''))
                has_changed = True
                for announcement in chain.get_announcements(best_chain, link_matrix, users):
                    send_message(bot, announcement)



            # Get rid of old non-existent links if the chain passes through only real links
            purge_count = 0
            if all_valid:
                for linker_id in link_matrix:
                    for link_id in link_matrix:
                        if link_matrix[linker_id][link_id] is matrix.State.Old:
                            link_matrix[linker_id][link_id] = matrix.State.Empty
                            purge_count += 1
                if purge_count:
                    print(f'Purged {purge_count} old links!')

            if has_changed or purge_count:
                print('Saving link matrix...')
                matrix.save(link_matrix)



            # Get rid of users who are not in the group and not in the best chain
            # td:replace best chain with .extend of all chains
            if all_valid:
                best_chain = set(best_chain)
                new_users = userdb.new()
                for user_id in users:
                    if user_id in best_chain or is_userid_in_group(bot, user_id):
                        new_users[user_id] = users[user_id]

                purge_count = len(users) - len(new_users)
                if purge_count:
                    users = new_users
                    print(f'Purged {purge_count} non-group members(s)! Saving userdb...')
                    userdb.save(users)


            exit()
            time.sleep(60)
        except Exception as e:
            print('Encountered exception while running main loop:', e)
            raise e

if __name__ == '__main__':
    main()