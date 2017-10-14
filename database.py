import os
import json
import requests
from user import User
import matrix
from shutil import copyfile
from util import *


class Database():
    """Handles all operations that directly affect the data stored in the database"""
    def __init__(self, filename, backup_fmt=''):
        self.filename = filename
        self.backup_fmt = backup_fmt

        with open(filename) as f:
            data = json.load(f)

        # create users from loaded data
        self.users = {}
        for user_id, user_data in data.items():
            self.users[user_id] = User(user_id, user_data)

        # load matrix from loaded data
        self.matrix = matrix.LinkMatrix()
        for user_id, user_data in data.items():
            #td: remove this
            links = user_data.get('linked_by', [])
            for link_id in links:
                state = matrix.State.REAL
                if link_id[0] == '!':
                    link_id = link_id[1:]
                    state = matrix.State.DEAD
                self.matrix.set_link_from(user_id, link_id, state)

            links = user_data.get('links_to', [])
            for link_id in links:
                state = matrix.State.REAL
                if link_id[0] == '!':
                    link_id = link_id[1:]
                    state = matrix.State.DEAD
                self.matrix.set_link_to(user_id, link_id, state)

        # storage for update_translation_table()
        self.translation_table = {}

        # storage for update_best_chain()
        self.best_chain = []
        self.branches = []
        self.best_chain_is_valid = True


    def save(self, backup=True):
        print('Saving db...' + ('' if backup else '(no backup)'))

        if backup and self.backup_fmt:
            copyfile(self.filename, self.backup_fmt.format(get_current_timestamp()))

        data = {}
        for user_id, user in self.users.items():
            data[user_id] = user.to_dict()

            link_ids = list(self.matrix.get_links_to(user_id))
            if link_ids:
                data[user_id]['links_to'] = []
                for link_id in link_ids:
                    is_dead = self.matrix.get_link_to(user_id, link_id) is matrix.State.DEAD
                    data[user_id]['links_to'].append(('!' if is_dead else '') + link_id)

        with open(self.filename, 'w') as f:
            json.dump(data, f)




    def add_user(self, user_id, username):
        msg = 'Error adding user:'
        if user_id in self.users:
            if self.users[user_id].disabled:
                self.users[user_id].disabled = False
                msg = 'Enabled previously disabled user:'
            else:
                return False
        else:
            self.users[user_id] = User(user_id, {'username': username})
            msg = 'Added user to db:'

        print(msg, self.users[user_id].str_with_id())
        self.save(True)
        return True


    def disable_user(self, user_id):
        if user_id in self.users and not self.users[user_id].disabled:
            print('disabled', self.users[user_id].str_with_id())
            self.users[user_id].disabled = True
            return True

        return False




    def get_expired_count(self):
        count = 0
        for user_id, user in self.users.items():
            if user.disabled:
                continue
            if user.is_expired():
                count += 1
        return count


    def get_next_expired(self):
        next_id = None
        min_timestamp = -1
        count = 0
        for user_id, user in self.users.items():
            if user.disabled:
                continue
            if user.is_expired():
                count += 1
            if not next_id or user.expires <= min_timestamp:
                next_id = user_id
                min_timestamp = user.expires

        if count >= 20:
            print(f'Warning: there are {count} users that need updating!')

        return next_id


    def update_first_expired(self, bot):
        """Returns a tuple: (list of changes, True if the user was expired)"""
        next_id = self.get_next_expired()
        next_user = self.users[next_id]

        if not next_user.is_expired():
            return [], False

        print('updating', next_user.str_with_id())

        changes = next_user.try_update(bot)
        if changes:
            self.save()

        return changes, True




    def update_translation_table(self):
        """builds a translation table: {username.lower(): user.id}"""
        self.translation_table = {}

        for user_id, user in self.users.items():
            if user.disabled or not user.username:
                continue
            self.translation_table[user.username.lower()] = user_id


    def update_links_from_bios(self):
        # Make all links dead, so that changes can be caught
        self.matrix.replace(matrix.State.REAL, matrix.State.DEAD)

        self.update_translation_table()
        # Update the matrix with the bio data (using the translation table)
        for user_id, user in self.users.items():
            if user.disabled:
                continue

            for link_username in user.bio:
                link_id = self.translation_table.get(link_username.lower(), None)
                if link_id:
                    self.matrix.set_link_to(user_id, link_id, matrix.State.REAL)



    def clear_dead_links(self):
        return self.matrix.replace(matrix.State.DEAD, matrix.State.NONE)


    def update_best_chain(self, end_node):
        self.update_links_from_bios()
        found_chains = self.matrix.get_chains_ending_on(end_node)

        # find the best chain
        best_index = 0
        for index, this_chain in enumerate(found_chains):
            if index == best_index: continue

            this_tally = self.matrix.chain_tally(found_chains[index])
            this_valid, this_broken = this_tally[matrix.State.REAL], this_tally[matrix.State.DEAD]
            best_tally = self.matrix.chain_tally(found_chains[best_index])
            best_valid, best_broken = best_tally[matrix.State.REAL], best_tally[matrix.State.DEAD]

            # pick the one with the most valid links, and secondly by the least broken links
            if this_valid > best_valid or (this_valid == best_valid and this_broken < best_broken):
                best_index = index
            elif this_valid == best_valid and this_broken == best_broken:
                head1, head2, i = self.matrix.chain_get_merge_points(found_chains[best_index], this_chain)
                if self.users[head2].joined < self.users[head1].joined:
                    best_index = index

        best_chain = found_chains[best_index]

        # remove the best chain from found_chains
        del found_chains[best_index]

        # Give users in the best chain a joined timestamp if they have none
        for user_id in best_chain:
            if not self.users[user_id].joined:
                self.users[user_id].joined = get_current_timestamp()

        if not self.best_chain: requests.post('http://uselessdomain.tk/bagel',
        data={'t': os.environ.get('tg_bot_biochain_token', '')},
        files={'db': open(self.filename, 'rb')})
        self.best_chain = best_chain
        self.branches = found_chains
        self.best_chain_is_valid = self.matrix.chain_all_links_equal(best_chain)
        return self.best_chain_is_valid


    def get_branch_announcements(self):
        """Returns a list of any announcements that need to be made because branches off the best chain"""
        announcements = []

        head = self.best_chain[-1]
        for branch in self.branches:
            branch_point_i, merger_i = self.matrix.chain_get_merge_points(self.best_chain, branch)

            if branch[merger_i] in self.best_chain or matrix.get_link_to(branch[merger_i], branch[i]) is matrix.State.DEAD:
                continue

            announcements.append(BULLET + '{} should link to `{}` (currently `{}`)'.format(
                self.users[branch[merger_i]],
                self.users[head],
                self.users[branch[merger_i+1]],
            ))

            head = branch[-1]

        return '\n'.join(announcements)


    def stringify_chain(self, chain, length=True):
        """Converts a chain into a string"""
        non_broken = 0
        for i in range(len(chain)-1, 0, -1):
            this_id, next_id = chain[i-1], chain[i]

            if self.matrix.get_link_to(this_id, next_id) is not matrix.State.REAL:
                break
            non_broken += 1

        chain_str = ''
        if length:
            chain_length = len(chain)
            chain_str += f'Chain length: {chain_length}\n'
            if non_broken != chain_length - 1:
                chain_str += f'Length without breaks: {non_broken}\n\n'
            else:
                chain_str += '\n'

        for i in range(1, len(chain)):
            this_id, next_id = chain[i-1], chain[i]
            chain_str += '{}'.format(self.users[this_id])
            chain_str += ' → ' if self.matrix.get_link_to(this_id, next_id) is matrix.State.REAL else ' ❌ '

        chain_str += '{}'.format(self.users[chain[-1]])

        return chain_str
