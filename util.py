import requests
import html
import re
import telegram

RE_SCRAPE_BIO = re.compile(r'<meta +property="og:description" +content="(.+?)".*>')
RE_USERNAME = re.compile(r'@([a-zA-Z][\w\d]{4,31})')
CHAT_ID = -1001113029151


def get_userids_from_bio(db, username):
    """
    Scrapes the bio from t.me/username
    Returns a list of user_ids of all valid links to users that we know
    """

    r = requests.get(f'http://t.me/{username}')
    if not r.ok:
        print(f'Request for @{username}\'s bio failed')
        return []

    bio = RE_SCRAPE_BIO.findall(r.text)
    if not bio:
        return []

    ids = []
    for link_username in RE_USERNAME.findall(html.unescape(bio[0])):
        if link_username.lower() == username.lower():
            continue

        for this_id, this_data in db.items():
            if link_username.lower() == this_data['username'].lower():
                ids.append(this_id)

    return ids



def send_message(bot, text):
    """Prints a message and then sends it via the bot to the chat"""
    if not text:
        return
        
    print('out:', text)
    return bot.sendMessage(
        chat_id=CHAT_ID,
        text=text,
        parse_mode='Markdown',
    )



def get_userid_username(bot, user_id):
    """Returns the username of a chat_id, may return None if the user is not in the group"""
    try:
        user = bot.getChatMember(CHAT_ID, user_id).user
        return user.username if hasattr(user, 'username') else ''
    except Exception as e:
        print(f'I don\'t know who {user_id} is:', e)

    return None