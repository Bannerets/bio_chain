import os
import json
import requests
from user import User
import matrix

class Database():
    """Handles all operations that directly affect the data stored in the database"""
    def __init__(self, filename):
        self.filename = filename

        with open(filename) as f:
            data = json.load(f)

        # create users from loaded data
        self.users = {}
        for user_id, user_data in data.items():
            self.users[user_id] = User(user_id, user_data)
            print(self.users[user_id].to_dict())

        # setup matrix from loaded data
        self.matrix = matrix.LinkMatrix()
        for user_id, user_data in data.items():
            links = user_data.get('linked_by', [])
            for link in links:
                self.matrix.set_link_from(user_id, link, matrix.State.DEAD)

        self.update_links_from_bios()


    def get_translation_table(self):
        """build a translation table: {username.lower(): user.id}"""
        tr_table = {}

        for user_id, user in self.users.items():
            if user.disabled or not user.username:
                continue
            tr_table[user.username.lower()] = user_id

        return tr_table


    def update_links_from_bios(self):
        # Make all links dead, so that changes can be caught
        self.matrix.replace(matrix.State.REAL, matrix.State.DEAD)

        tr_table = self.get_translation_table()
        # Update the matrix with the bio data (using the translation table)
        for user_id, user in self.users.items():
            if user.disabled:
                continue

            for link_username in user.bio:
                link_id = tr_table.get(link_username.lower(), None)
                if link_id:
                    self.matrix.set_link_to(user_id, link_id, matrix.State.REAL)

        return tr_table

if __name__ == '__main__':
    database = Database('example_db.json')