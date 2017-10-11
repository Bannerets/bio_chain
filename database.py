import json
import requests
from user import User

class db():
    """Handles all operations that directly affect the data stored in the database"""
    def __init__(self, filename):
        self.filename = filename

        with open(filename) as f:
            data = json.load(f)

        # create users from loaded data
        self.users = []
        for user_id, user_data in data.items():
            self.users.append(User(user_id, user_data))
            print(self.users[-1].to_dict())


if __name__ == '__main__':
    database = db('example_db.json')
