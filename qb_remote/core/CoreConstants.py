import datetime
import time
import sys
import os
import re

START_TIME_PRECISE = time.perf_counter()
# ha, subtracting here makes it suuuper close the psutil.create_time()
START_TIME_FLOAT = time.time() - START_TIME_PRECISE
START_TIME = int(START_TIME_FLOAT)

START_TIME_DATE = datetime.datetime.now()
START_TIME_PRETTY = datetime.datetime.strftime(START_TIME_DATE, "%Y-%m-%d %H:%M:%S")

BRAND = "qBittorrent Remote GUI"

TORRENT_CACHE_TIME_SECONDS = 3


TORRENT_METADATA_SYNC_RATE_MS = 5 * 1000


TORRENT_PRIORITY_DO_NOT_DOWNLOAD = 0
TORRENT_PRIORITY_NORMAL = 1
TORRENT_PRIORITY_HIGH = 6
TORRENT_PRIORITY_MAXIMUM = 7

# see https://en.wikipedia.org/wiki/Magnet_URI_scheme
MAGNET_LINK_REGEX = re.compile(r"(magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:&(?:xt|dn|xl|tr|ws|as|xs|kt|mt|so|x\.pe)=[^\s]+)*)")