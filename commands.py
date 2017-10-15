import commands
for attr in dir(commands):
    if attr.startswith('cmd_'):
        print(attr, getattr(commands, attr).__doc__)

from util import *

def cmd_help(db, update, directed, command_args):
    """test"""
    if not directed:
        return

    update.message.reply_text('`insert help text here`', parse_mode='Markdown')

def cmd_pin(db, update, directed, command_args):
    """pin_doc"""
    if update.message.chat.id != CHAT_ID:
        update.message.reply_text('Sorry, I can only do that in the official group')
        return

    update.message.reply_text('^', reply_to_message_id=LAST_PIN.get())

