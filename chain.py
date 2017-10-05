import matrix

END_NODE = '51863899'
BRANCH_SLICE = 5
BULLET = '∙ '


def is_valid(chain, link_matrix):
    """Returns True if all the links in the chain are valid"""
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is not matrix.State.Current:
            return False

    return True


def tally(chain, link_matrix):
    """Counts the number of broken and valid links in a chain"""
    current, broken = 0, 0
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is matrix.State.Current:
            current += 1
        elif link_matrix[this_id][next_id] is matrix.State.Old:
            broken += 1

    return current, broken


def find_merge_head(chain1, chain2):
    """Finds the nodes just before the merge of two chains"""
    i = 0
    max1, max2 = len(chain1)-1, len(chain2)-1
    while chain1[min(i, max1)] == chain2[min(i, max2)] and (i < max1 or i < max2):
        i += 1

    return chain1[min(i, max1)], chain2[min(i, max2)], max(i - 1, 0)



def find_best(link_matrix, db):
    """
    Returns a tuple:
    [0] = the best possible chain from link_matrix
    [1] = a list of all other found chains
    [2] = True if all links in best chain are valid
    """
    found_chains = []

    pending_chains = [[END_NODE]]


    while pending_chains:
        # grab a chain from the stack
        this_chain = pending_chains.pop()
        last_link = this_chain[-1]
        is_end = True

        # iterate through all the links that we can go to
        for next_link in link_matrix[last_link]:
            # if next_link is valid and we have not visited it before
            if link_matrix[last_link][next_link] is not matrix.State.Empty and next_link not in this_chain:
                # since we can reach a node then this is not the end
                is_end = False
                # add [this_chain + next_link] to pending_chains
                new_chain = this_chain[:]
                new_chain.append(next_link)
                pending_chains.append(new_chain)

        # if last_link doesn't go anywhere, then add it to our found chains
        if is_end:
            found_chains.append(this_chain)


    # find the best chain
    best_index = 0
    for index, this_chain in enumerate(found_chains):
        if index == best_index: continue

        this_valid, this_broken = tally(found_chains[index], link_matrix)
        best_valid, best_broken = tally(found_chains[best_index], link_matrix)

        # pick the one with the most valid links, and secondly by the least broken links
        if this_valid > best_valid or (this_valid == best_valid and this_broken < best_broken):
            best_index = index
        elif this_valid == best_valid and this_broken == best_broken:
            head1, head2, i = find_merge_head(found_chains[best_index], this_chain)
            if db[head2].get('joined', 9999999999) < db[head1].get('joined', 9999999999):
                best_index = index

    best_chain = found_chains[best_index]

    # remove the best chain from found_chains
    del found_chains[best_index]

    return best_chain, found_chains, is_valid(best_chain, link_matrix)



def flood_fill(link_matrix):
    """Returns a set of all reachable nodes from END_NODE"""
    nodes = {END_NODE}

    pending_chains = [[END_NODE]]

    while pending_chains:
        # grab a chain from the stack
        this_chain = pending_chains.pop()
        last_link = this_chain[-1]

        # iterate through all the links that we can go to
        for next_link in link_matrix[last_link]:
            if link_matrix[last_link][next_link] is matrix.State.Current and next_link not in this_chain:
                # ...and add them to our node set
                nodes.add(next_link)
                # add [this_chain + next_link] to pending_chains
                new_chain = this_chain[:]
                new_chain.append(next_link)
                pending_chains.append(new_chain)

    return nodes




def stringify(chain, link_matrix, db, length=True):
    """Converts a chain into a string"""
    non_broken = 0
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        if link_matrix[this_id][next_id] is not matrix.State.Current:
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

    chain = chain[::-1]
    
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        chain_str += '@{}'.format(db[this_id]['username'])
        chain_str += ' → ' if link_matrix[next_id][this_id] is matrix.State.Current else ' ❌ '

    chain_str += '@{}'.format(db[chain[-1]]['username'])

    return chain_str



def summary(chain, link_matrix, db):
    """Converts a chain into a shorter debug string than stringify_chain"""
    def short_name(name):
        nonlocal names
        end = 3
        while name[:end] in names and end <= len(name):
            end += 1
        names.add(name[:end])
        return name[:end]

    chain_str = 'scr:{} len:{} '.format(tally(chain, link_matrix), len(chain))
    chain = chain[::-1]
    names = set()
    
    for i in range(1, len(chain)):
        this_id, next_id = chain[i-1], chain[i]
        chain_str += '@{}'.format(short_name(db[this_id]['username']))
        chain_str += ' → ' if link_matrix[next_id][this_id] is matrix.State.Current else ' ❌ '

    chain_str += '@{}'.format(short_name(db[chain[-1]]['username']))

    return chain_str



def get_branch_announcements(best_chain, branches, link_matrix, db):
    """Returns a list of any announcements that need to be made because branches off the best chain"""
    head = best_chain[-1]
    for branch in branches:
        branch_point, merger, i = find_merge_head(best_chain, branch)

        if merger in best_chain or link_matrix[branch[i]][merger] is matrix.State.Old:
            continue

        slice_count = len(branch) - i - BRANCH_SLICE
        announcements.append(BULLET + '@{} should link to `@{}` (currently `@{}`)'.format(
            db[merger]['username'],
            db[head]['username'],
            db[branch[i]]['username']
        ))

        head = branch[-1]

    return '\n'.join(announcements)
