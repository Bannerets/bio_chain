import requests
import html
import re

RE_SCRAPE_BIO = re.compile(r'<meta +property="og:description" +content="(.+?)".*>')
RE_USERNAME = re.compile(r'@([a-zA-Z][\w\d]{4,31})')

def scrape_bio_usernames(username):
    """
    Scrapes the bio from t.me/username
    Returns a list of user_ids of all valid links to users that we know
    """

    r = requests.get(f'http://t.me/{username}')
    if not r.ok:
        print(f"Request for @{username}'s bio failed")
        return []

    bio = RE_SCRAPE_BIO.findall(r.text)
    if not bio:
        return []

    return RE_USERNAME.findall(html.unescape(bio[0]))
