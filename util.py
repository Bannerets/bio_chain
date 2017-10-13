import time
CHAT_ID = -1001145055784


def get_current_timestamp():
    return round(time.time())


def markdown_escape(s, code=False):    
    s = str(s).replace('`', '\\`')

    if code:
        return s

    return s.replace('*', '\\*').replace('_', '\\_')

def caseless_set_eq(list1, list2):
    return {v.lower() for v in list1} == {v.lower() for v in list2}