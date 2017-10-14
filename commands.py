from util import *

def help(db, update, directed, command_args):
    if not directed:
        return

    update.message.reply_text('`insert help text here`', parse_mode='Markdown')

def pin(db, update, directed, command_args):
    if update.message.chat.id != CHAT_ID:
        update.message.reply_text('Sorry, I can only do that in the official group')
        return

    update.message.reply_text('^', reply_to_message_id=LAST_PIN.get())