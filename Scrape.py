from urllib.request import Request, urlopen
import os
import re
import codecs
import json
import time
import sys
import math

# Update this line with your API key
ME_COOKIE = ''

SAVE_DIR = 'scraped/'
DATA_FILE = SAVE_DIR + 'all_comments.txt'
READ_CACHE_ONLY = False

ALL_COMMENTS = True
ALL_COMMENTS_LEN_MIN = 16
ALL_COMMENTS_LEN_MAX = 420

COMMENT_MIN_CONFIDENCE = 0.3
TAG_MIN_CONFIDENCE = 0.2

# Create directory to hold downloaded data
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

# Try to load the existing database so far
all_comments = {}
try:
    with codecs.open(DATA_FILE, 'r', encoding='utf-8') as fin:
        for line in fin:
            iid, pid, tags, comment = line[:-1].split('~')
            all_comments[vid] = (tags, comment)
except:
    pass


def scrape_top(flags):
    LAST_POST = ''
    TIME_PER_PAGE = 0
    PAGE = -1
    TIMER = time.perf_counter()
    while True:
        PAGE += 1
        # Setup strings
        TOP_POSTS_URL = 'https://pr0gramm.com/api/items/get?flags=' + \
            str(flags) + '&promoted=1'
        if LAST_POST != '':
            TOP_POSTS_URL += '&older=' + str(LAST_POST)
            new_timer = time.perf_counter()
            TIME_PER_PAGE = new_timer - TIMER
            TIMER = new_timer
            print("\nFinished page in " + str(round_half_up(TIME_PER_PAGE)) +
                  "s (" + str(round_half_up(1/(TIME_PER_PAGE/120))) + "/s)")
            print("Getting posts older than " + str(LAST_POST))
        SAVE_FILE = SAVE_DIR + 'top_' + \
            str(flags) + "_" + str(LAST_POST) + '.txt'
        data_out = codecs.open(DATA_FILE, 'a', encoding='utf-8')

        # Download the query (or load from file if cached)
        if LAST_POST != '' and os.path.isfile(SAVE_FILE):
            query_str = ""
            with codecs.open(SAVE_FILE, 'r', encoding='utf-8') as fin:
                query_str = fin.read()
        else:
            if READ_CACHE_ONLY:
                break
            query = Request(TOP_POSTS_URL)
            query.add_header('cookie', 'me=' + ME_COOKIE)
            query_str = urlopen(query, timeout=10).read().decode('utf-8')
            with codecs.open(SAVE_FILE, 'w', encoding='utf-8') as fout:
                fout.write(query_str)
            time.sleep(0.5)

        # Ignore if query is empty
        if len(query_str) == 0:
            print("===== WARNING: Empty Response =====")
            return

        # Loop over all videos in the playlist
        query_json = json.loads(query_str)
        items = query_json['items']
        for idx, item in enumerate(items):
            # Get the post information
            iid = item['id']
            pid = item['promoted']
            if iid in all_comments:
                continue

            # Scrape Justin Y comments from the video
            try:
                item_info = scrape_item(iid)
                tags = item_info[0]
                good_comments = item_info[1]
            except Exception as e:
                print(e)
                print("Cant recover. Skipping item " + str(iid))
                continue

            # Save all the good comments
            for good_comment in good_comments:
                comment = good_comment.replace(
                    '\n', ' . ').replace('\r', ' . ').replace('~', ' ')
                data_out.write(str(iid) + '~' + str(pid) + '~' +
                               tags + '~' + comment + '\n')
                all_comments[iid] = (tags, comment)
            print_progress(PAGE, pid, idx, TIME_PER_PAGE, "    Loaded " + str(len(good_comments)) +
                           " comments for post " + str(pid) + " (" + str(iid) + ")")

        # Get the next page to process or quit if done
        data_out.close()
        if not query_json['atEnd']:
            LAST_POST = pid
        else:
            break


def scrape_item(iid):
    good_comments = []
    # Setup strings
    COMMENT_URL = 'https://pr0gramm.com/api/items/info?itemId=' + str(iid)
    SAVE_FILE = SAVE_DIR + 'itm_' + str(iid) + '.txt'

    # Download the query (or load from file if cached)
    if os.path.isfile(SAVE_FILE):
        query_str = ''
        with codecs.open(SAVE_FILE, 'r', encoding='utf-8') as fin:
            query_str = fin.read()
    else:
        if READ_CACHE_ONLY:
            return []
        request = Request(COMMENT_URL)
        request.add_header('cookie', 'me=' + ME_COOKIE)
        query_str = urlopen(request).read().decode('utf-8')
        with open(SAVE_FILE, 'w', encoding='utf-8') as fout:
            fout.write(query_str)
        time.sleep(0.5)

    query_json = json.loads(query_str)
    tags = query_json['tags']
    tags.sort(key=lambda t: t['confidence'], reverse=True)
    combined_tags = ''

    for i in range(len(tags)):
        tag = tags[i]
        if tag['confidence'] < TAG_MIN_CONFIDENCE and not is_flag(tag['tag']):
            break
        tag_value = tag['tag'].replace('\n', ' . ').replace(
            '\r', ' . ').replace('~', ' ').replace('#*#', ' ')
        if len(combined_tags) == 0:
            combined_tags = tag_value
        else:
            combined_tags += '#*#' + tag_value

    comments = query_json['comments']
    # Look for popular comments and add them
    for i in range(len(comments)):
        comment = comments[i]
        if comment['parent'] != 0:
            continue
        if comment['confidence'] < COMMENT_MIN_CONFIDENCE:
            continue

        text = comment['content']
        if len(text) < ALL_COMMENTS_LEN_MIN or len(text) > ALL_COMMENTS_LEN_MAX:
            continue
        good_comments.append(text)

    # Return whatever was found
    return (combined_tags, good_comments)


def is_flag(tag):
    tag = tag.lower()
    return tag == 'nsfp' or tag == 'nsfw' or tag == 'nsfl'


def print_progress(page, current, index, tpp, last_action):
    sys.stdout.write(last_action + "\n")
    total_processed = 1 + index + page * 120
    global_progress = 100 / (current + total_processed) * total_processed
    sys.stdout.write("Total: " +
                     str(round_half_up(global_progress)) + "%" +
                     "  Page " + str(page) + ": " + str(round_half_up(100/119*index)) +
                     "% ETA: " + str(round_half_up(current / 120 * tpp / 3600)) + "h            ")
    sys.stdout.write('\r')
    sys.stdout.flush()


def round_half_up(n, decimals=2):
    multiplyer = 10 ** decimals
    return math.floor(n*multiplyer + 0.5)/multiplyer


scrape_top(15)
