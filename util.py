import requests
import html
import re
import telegram
import time

RE_SCRAPE_BIO = re.compile(r'<meta +property="og:description" +content="(.+?)".*>')
RE_USERNAME = re.compile(r'@([a-zA-Z][\w\d]{4,31})')
CHAT_ID = -1001145055784


def get_usernames_from_bio(db, user_id):
    """
    Scrapes the bio from t.me/username
    Returns a set of usernames
    """
    username = db[user_id]['username']
    if not username:
        print(f'Request for blank username', user_id)
        return set()

    r = requests.get(f'http://t.me/{username}')
    if not r.ok:
        print(f'Request for @{username}\'s bio failed ({r.status_code})')
        return set()

    bio = RE_SCRAPE_BIO.findall(r.text)
    if not bio:
        return set()

    bio_usernames = set()
    for bio_username in RE_USERNAME.findall(html.unescape(bio[0])):
        if bio_username.lower() == username.lower():
            continue
        bio_usernames.add(bio_username)

    return bio_usernames



def send_message(bot, text, chat_id=CHAT_ID):
    """Prints a message and then sends it via the bot to the chat"""
    if not text:
        return
        
    print('out:', text)

    return bot.sendMessage(
        chat_id=chat_id,
        text=text,
        parse_mode='Markdown',
    )



def get_username_from_id(bot, user_id):
    """Returns the username of a chat_id, may raise an exception if the user is not in the group"""
    user = bot.getChatMember(CHAT_ID, user_id).user
    return user.username or ''



def current_timestamp():
    return int(time.time())

def markdown_escape(s, code=False):    
    s = s.replace('`', '\\`')

    if code:
        return s

    return s.replace('*', '\\*').replace('_', '\\_')

def username_str(username, code=False):
    return '@'+markdown_escape(username) or '[no username]'
