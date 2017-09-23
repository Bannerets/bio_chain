import userdb
import matrix

CHAT_ID = -1001113029151


def is_valid(chain, link_matrix):
    """Returns True if all the links in the chain are valid"""
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is not matrix.State.Current:
            return False

    return True



def valid_count(chain, link_matrix):
    valid = 0
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is matrix.State.Current:
            valid += 1

    return valid



def find_best(link_matrix, userdb):
    """
    Returns a tuple:
    [0] = the best possible chain (most valid links) from link_matrix
    [2] = True if the longest chain is valid
    """
    best_chain = []
    best_chain_valid = -1

    pending_chains = []

    # add every possible head to pending_chains
    for head_id in link_matrix:
        pending_chains.append([head_id])

    while pending_chains:
        # grab a chain from the stack
        this_chain = pending_chains.pop()
        last_link = this_chain[-1]

        # iterate through all the links that the last_link in this_chain links to
        for next_link in link_matrix[last_link]:
            # if next_link is valid and we have not visited it before
            if link_matrix[last_link][next_link] is not matrix.State.Empty and next_link not in this_chain:
                # add [this_chain + next_link] to pending_chains
                new_chain = this_chain[:]
                new_chain.append(next_link)
                pending_chains.append(new_chain)

        # if last_link is the end, then test if this is the longest/best chain
        if last_link == '51863899':
            this_valid = valid_count(this_chain, link_matrix)
            if this_valid > best_chain_valid:
                best_chain_valid = this_valid
                best_chain = this_chain

    print('', stringify_short(best_chain, link_matrix, userdb))
    return best_chain, is_valid(best_chain, link_matrix)



def stringify(chain, link_matrix, userdb):
    """Converts a chain into a string"""
    chain_str = f'Chain length: {len(chain)}\n\n'
    
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        chain_str += f'@{userdb[this_id].username}'
        chain_str += ' → ' if link_matrix[this_id][next_id] is matrix.State.Current else ' ❌ '

    chain_str += f'@{userdb[chain[-1]].username}'

    return chain_str



def stringify_short(chain, link_matrix, userdb):
    """Converts a chain into a shorter debug string than stringify_chain"""
    def short_name(name):
        nonlocal names
        end = 3
        while name[:end] in names and end <= len(name):
            end += 1
        names.add(name[:end])
        return name[:end]

    chain_str = f'({len(chain)}) '
    names = set()
    
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        chain_str += '@{}'.format(short_name(userdb[this_id].username))
        chain_str += ' → ' if link_matrix[this_id][next_id] is matrix.State.Current else ' ❌ '

    chain_str += '@{}'.format(short_name(userdb[chain[-1]].username))

    return chain_str



def get_announcements(chain, link_matrix, userdb):
    """Returns a list of any announcements that need to be made because of broken links in a chain"""
    announcements = []

    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is not matrix.State.Current:
            announcements.append(f'@{userdb[this_id].username} has no valid links (should be `@{userdb[next_id].username}`)!')
            for link_id in get_links_to(link_matrix, this_id):
                announcements.append(f'@{userdb[link_id].username} should update their bio because of this!')

    #td better branch detection
    for user_id in userdb:
        if user_id not in chain and matrix.user_has_valid_link(user_id, link_matrix):
            announcements.append(f'Suggestion: @{userdb[user_id].username} should link to `@{userdb[chain[0]].username}`!')

    return announcements