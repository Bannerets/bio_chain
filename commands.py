import commands
from util import *


def cmd_help(db, update, directed, command_args):
    """shows this message"""
    if not directed:
        return

    update.message.reply_text(help_text, parse_mode='Markdown')

def cmd_pin(db, update, directed, command_args):
    """quotes the current pin message"""
    if update.message.chat.id != CHAT_ID:
        update.message.reply_text('Sorry, I can only do that in the official group')
        return

    update.message.reply_text('^', reply_to_message_id=LAST_PIN.get())


help_text = []
for attr in dir(commands):
    if attr.startswith('cmd_'):
        help_text.append('/{} - {}'.format(
            attr[4:],
            getattr(commands, attr).__doc__ or 'no help available'
        ))
help_text = '\n'.join(help_text)