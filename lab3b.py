#!/usr/local/cs/bin/python3
import sys


superblock, group, freeblocks, freeinodes, INODE_TO_BLOCKS = {}, {}, {}, {}, {}
dirents = []
inodes = []
indirects = []

if_inconsistency = 0

def init():
    # global superblock
    if len(sys.argv) < 2:
        handle_error("incorrect usage: ./lab3b [file]\n", 1)
    else:
        filename = sys.argv[1]

    with open(filename, "r") as f:
        for line in f:
            line = line.strip().split(',')
            tag = line[0]
            if tag == "SUPERBLOCK":
                read_superblock(line)
            elif tag == "GROUP":
                read_group(line)
            elif tag == "BFREE":
                read_free_blocks(line)
            elif tag == "IFREE":
                read_free_inodes(line)
            elif tag == "INODE":
                inodes.append(read_inode(line))
            elif tag == "DIRENT":
                dirents.append(read_dirent(line))
            elif tag == "INDIRECT":
                indirects.append(read_indirect(line))

    superblock['begin_block'] = 1 + group['ino_bitmap'] + (superblock['ino_size'] * group['ino_cnt'] ) // superblock['blk_size']
    # print("superblock: ", superblock)

def audit_block():
    for inode in inodes:
        for i, b in enumerate(inode["blocks"]):
            head = check_block_type(b)
            block_type, offset = check_offset(i)

            if head == 'INVALID' or head == "RESERVED":
                sys.stdout.write(f"{head} {block_type} {b} IN INODE {inode['idx']} AT OFFSET {offset}\n")

    BLOCK_TO_INODES = check_duplicates()
    # print("BLOCK_TO_INODES: ", BLOCK_TO_INODES)
    check_others(BLOCK_TO_INODES)


def check_others(BLOCK_TO_INODES):
    for b in range(superblock['begin_block'], superblock['blk_cnt']):
        if (b not in freeblocks) and (b not in BLOCK_TO_INODES):
            sys.stdout.write(f"UNREFERENCED BLOCK {b}\n")

    for b in range(1, superblock['blk_cnt']):
        if (b in freeblocks) and (b in BLOCK_TO_INODES or b < superblock['begin_block']):
            sys.stdout.write(f"ALLOCATED BLOCK {b} ON FREELIST\n")

def check_duplicates():
    level_dict = {0: 'BLOCK', 1: 'INDIRECT BLOCK', 2: 'DOUBLE INDIRECT BLOCK', 3: 'TRIPLE INDIRECT BLOCK'}
    # check two blocks are referenced by the same inode
    BLOCK_TO_INODES = {}
    for k, B in INODE_TO_BLOCKS.items():
        for block, level, offset in B:
            if block not in BLOCK_TO_INODES:
                BLOCK_TO_INODES[block] = []
            else:
                block_type = level_dict[level]
            BLOCK_TO_INODES[block].append((k, block, level, offset))

    for key, value in BLOCK_TO_INODES.items():
        if(len(value) > 1):
            for inode in value:
                sys.stdout.write(f'DUPLICATE {level_dict[inode[2]]} {inode[1]} IN INODE {inode[0]} AT OFFSET {inode[3]}\n')

    return BLOCK_TO_INODES

def check_block_type(b):
    if b < 0 or b > superblock["blk_cnt"]:
        return 'INVALID'
    elif b < superblock['begin_block'] and b>0:
        return 'RESERVED'
    else:
        return ''


def check_offset(i):
    num_blocks = superblock['blk_size'] // 4
    if i < 12:
        block_type = 'BLOCK'
        offset = i
    elif i == 12:
        block_type = 'INDIRECT BLOCK'
        offset = i
    elif i == 13:
        block_type = "DOUBLE INDIRECT BLOCK"
        offset = 12 + num_blocks
    elif i == 14:
        block_type = "TRIPLE INDIRECT BLOCK"
        offset = 12 + num_blocks + num_blocks*num_blocks
    return block_type, offset



def audit_inode_allocation():
    allocated_inodes = {}
    for inode in inodes:
        allocated_inodes[inode['idx']] = 1
        if inode['idx'] in freeinodes:
            sys.stdout.write(f"ALLOCATED INODE {inode['idx']} ON FREELIST\n")
    for i in range(superblock["inode_begin"], group["ino_cnt"] + 1):
        if (i not in allocated_inodes) and (i not in freeinodes):
            sys.stdout.write(f"UNALLOCATED INODE {i} NOT ON FREELIST\n")

def audit_directory_allocation():
    # count referenced by file
    inode_counts = {}
    for dirent in dirents:
        if dirent["inode_idx"] not in inode_counts:
            inode_counts[dirent["inode_idx"]] = 0
        inode_counts[dirent["inode_idx"]] += 1

    allocated_inodes = {}
    for inode in inodes:
        inode_link_count = 0
        allocated_inodes[inode["idx"]] = 1
        if inode["idx"] in inode_counts:
            inode_link_count = inode_counts[inode["idx"]]
        if inode_link_count != inode["link_cnt"]:
            sys.stdout.write(f"INODE {inode['idx']} HAS {inode_link_count} LINKS BUT LINKCOUNT IS {inode['link_cnt']}\n")

    # check invalid/unallocated inode
    for dirent in dirents:
        if (dirent["inode_idx"] < 1) or (dirent["inode_idx"] > superblock["ino_cnt"]):
            sys.stdout.write(f"DIRECTORY INODE {dirent['par_inode']} NAME {dirent['name']} INVALID INODE {dirent['inode_idx']}\n")
        elif dirent["inode_idx"] not in allocated_inodes:
            sys.stdout.write(f"DIRECTORY INODE {dirent['par_inode']} NAME {dirent['name']} UNALLOCATED INODE {dirent['inode_idx']}\n")

    # check parent inode
    parent_inode = {}
    for dirent in dirents:
        if dirent['name'] == '\'.\'':
            if dirent['inode_idx'] != dirent['par_inode']:
                sys.stdout.write(f"DIRECTORY INODE {dirent['par_inode']} NAME \'.\' LINK TO INODE {dirent['inode_idx']} SHOULD BE {dirent['par_inode']}\n")
        elif dirent['name'] == '\'..\'':
            pass
        else:
            parent_inode[dirent['inode_idx']] = dirent['par_inode']

    for dirent in dirents:
        if dirent['name'] == '\'..\'':
            if dirent['par_inode'] in parent_inode:
                if dirent['inode_idx'] != parent_inode[dirent['par_inode']]:
                    sys.stdout.write(f"DIRECTORY INODE {dirent['par_inode']} NAME \'..\' LINK TO INODE {dirent['inode_idx']} SHOULD BE {parent_inode[dirent['par_inode']]}\n")
            else:
                if dirent['inode_idx'] != dirent['par_inode']:
                    sys.stdout.write(f"DIRECTORY INODE {dirent['par_inode']} NAME \'..\' LINK TO INODE {dirent['inode_idx']} SHOULD BE {dirent['par_inode']}\n")



def read_indirect(line):
    indirect = {}
    indirect["inode_idx"] = int(line[1])
    indirect["level"] = int(line[2])
    indirect["logic_block_offset"] = int(line[3])
    indirect["par_block_index"] = int(line[4])
    indirect["ref_block_idx"] = int(line[5])

    if indirect["inode_idx"] not in INODE_TO_BLOCKS:
        INODE_TO_BLOCKS[indirect['inode_idx']] = []
    INODE_TO_BLOCKS[indirect["inode_idx"]].append((indirect['ref_block_idx'], indirect['level']-1, indirect['logic_block_offset']))
    return indirect

def read_dirent(line):
    dirent = {}
    dirent["par_inode"] = int(line[1])
    dirent["logic_offset"] = int(line[2])
    dirent["inode_idx"] = int(line[3])
    dirent["entry_len"] = int(line[4])
    dirent["name_len"] = int(line[5])
    dirent["name"] = line[6]
    return dirent

def read_inode(line):
    inode = {}
    inode["idx"] = int(line[1])
    inode["type"] = line[2]
    inode['owner'] = int(line[4])
    inode["group"] = int(line[5])
    inode["link_cnt"] = int(line[6])
    inode["file_size"] = int(line[10])
    inode["512_num_block"] = int(line[11])
    inode["blocks"] = list(map(int, line[12:]))

    for i, b in enumerate(inode["blocks"]):
        if b == 0:
            continue
        num_blocks = superblock['blk_size'] // 4
        if i < 12:
            l = 0
            offset = i
        if i == 12:
            l = 1
            offset = i
        if i == 13:
            l = 2
            offset = 12 + num_blocks
        if i == 14:
            l = 3
            offset = 12 + num_blocks + num_blocks*num_blocks

        if inode["idx"] not in INODE_TO_BLOCKS:
            INODE_TO_BLOCKS[inode['idx']] = []
        INODE_TO_BLOCKS[inode['idx']].append(
            (b, l, offset))

    return inode



def read_free_blocks(line):
    freeblocks[int(line[1])] = 1


def read_free_inodes(line):
    freeinodes[int(line[1])] = 1


def read_superblock(line):
    superblock['blk_cnt'] = int(line[1])
    superblock['ino_cnt'] = int(line[2])
    superblock['blk_size'] = int(line[3])
    superblock['ino_size'] = int(line[4])
    superblock['blk_per_gp'] = int(line[5])
    superblock['ino_per_gp'] = int(line[6])
    superblock['inode_begin'] = int(line[7])


def read_group(line):
    group['group_idx'] = int(line[1])
    group['blk_cnt'] = int(line[2])
    group['ino_cnt'] = int(line[3])
    group['free_blk_cnt'] = int(line[4])
    group['free_ino_cnt'] = int(line[5])
    group['blk_bitmap'] = int(line[6])
    group['ino_bitmap'] = int(line[7])
    group['inode_table'] = int(line[8])


def handle_error(error_msg, exit_num):
    sys.stderr.write(error_msg)
    sys.exit(exit_num)

if __name__ == '__main__':
    init()
    audit_block()
    audit_inode_allocation()
    audit_directory_allocation()

    if if_inconsistency:
        sys.exit(2)
    else:
        sys.exit(0)


