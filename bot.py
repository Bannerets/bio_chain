import os
import time
import telegram
import traceback

from database import Database
from file_string import FileString
from util import *

DATABASE_FILENAME = 'db.json'
END_NODE = '51863899'
LAST_CHAIN = FileString('last_chain.txt')
LAST_PIN = FileString('last_pin.txt')


def update_chain(bot, chain_text):
    print(chain_text)
    return True

    """
    Tries to post chain_text (editing the last message if possible)
    Returns True if chain_text was sent, False if not
    """
    if chain_text == LAST_CHAIN.get():
        return False

    if len(chain_text) >= 3000:
        send_message(bot, '@KateWasTaken Warning: The chain is approaching message character limit ({:.1%})'.format(
            len(chain_text) / 4096
        ))

    try:
        # try to edit our last pinned message
        message = bot.editMessageText(
            chat_id=CHAT_ID,
            message_id=LAST_PIN.get(),
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

            LAST_PIN.set(message.message_id)


    LAST_CHAIN.set(chain_text)

    return True


def send_message(bot, text, chat_id=CHAT_ID):
    """Prints a message and then sends it via the bot to the chat"""
    if not text:
        return
        
    print('out:', text)
    return

    return bot.sendMessage(
        chat_id=chat_id,
        text=text,
        parse_mode='Markdown',
    )


def get_update_users(update):
    """Yields the new user IDs and usernames associated with an update in the chat"""
    if update.message and update.message.chat.id == CHAT_ID:
        for user in update.message.new_chat_members:
            if not user.is_bot:
                yield str(user.id), user.username or ''
        user = update.message.from_user
        if not user.is_bot:
            yield str(user.id), user.username or ''


def handle_update(update):
    print(update)


def main():
    db = Database(DATABASE_FILENAME, 'bk/db{}.json')
    db.update_best_chain(END_NODE)

    bot = telegram.Bot(os.environ['tg_bot_biochain_token'])
    next_update_id = -100

    pending_changes = []
    while 1:
        try:
            try:
                updates = bot.getUpdates(offset=next_update_id)
            except telegram.error.TimedOut:
                updates = []

            for update in updates:
                handle_update(update)
                # Add users who are not in the db to the db
                for user_id, username in get_update_users(update):
                    db.add_user(user_id, username)


            # try to update the user who expires next
            changes, user_was_updated = db.update_first_expired(bot)
            if not user_was_updated:
                time.sleep(1)

            pending_changes.extend(changes)

            if db.get_expired_count() > 0 or not pending_changes:
                continue


            # update the link matrix with the bio data that we scraped
            tr_table = db.update_links_from_bios()
            # rebuild the best chain
            db.update_best_chain(END_NODE)

            # post the best chain if it's different to the old one
            if update_chain(bot, db.stringify_chain(db.best_chain)):
                send_message(bot, db.get_branch_announcements())

            for pending_change in pending_changes:
                print(pending_change)
            pending_changes.clear()

            # disable users who we failed to fetch a username for and aren't in the chain
            for user_id in db.users:
                if db.users[user_id].username_fetch_failed and user_id not in db.best_chain:
                    db.disable_user(user_id)

            # Get rid of old non-existent links if the chain passes through only real links
            if db.best_chain_is_valid:
                print('Purged {} dead links'.format( db.clear_dead_links() ))

            exit()
        except Exception as e:
            print('Encountered exception while running main loop:', type(e))
            #send_message(bot, '```\n{}\n{}```'.format(type(e), traceback.format_exc()), 232787997)
            raise e

if __name__ == '__main__':
    main()
