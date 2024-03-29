import datetime
import time
import pathlib
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

CONFIG_DIRECTORY = os.path.join(pathlib.Path.home(), ".config", "qBittorrent_Remote_GUI")
CONFIG_CLIENT_ID_FILE = os.path.join(CONFIG_DIRECTORY, "client_id")
CONFIG_CLIENT_SETTINGS = os.path.join(CONFIG_DIRECTORY, "settings.json")

# profile mode is designed if you want to share a remote client with multiple pc / people
# the idea is that each gui would have it's own 'profile' where only it's torrents show up
# it's supposed to be more of a soft lock as obviously anyone with the credentials can login
# it also gives each person their own folde for files, which works great, until 2 or more people add the same torrent
# then whoever added it first gets the files in their folder
DEFAULT_CLIENT_ID = "anonymous"
IS_PROFILE_MODE = False
# overwrites personal setting of the client id, using a hardware id instead
USE_HARDWARE_ID = False

# to manually set a root folder for all torrents,
# otherwise it will automatically use the default qbittorrent folder
USE_TORRENT_ROOT_FOLDER = False
TORRENT_ROOT_FOLDER = "/mnt"
PUBLIC_TORRENT_ROOT_FOLDER = "/mnt/public"

TORRENT_CACHE_TIME_SECONDS = 3


TORRENT_METADATA_SYNC_RATE_MS = 5 * 1000


TORRENT_PAUSED_PRIORITY = 1
TORRENT_ACTIVE_PRIORITY = 0

TORRENT_FILE_PRIORITY_DO_NOT_DOWNLOAD = 0
TORRENT_FILE_PRIORITY_NORMAL = 1
TORRENT_FILE_PRIORITY_HIGH = 6
TORRENT_FILE_PRIORITY_MAXIMUM = 7

# see https://en.wikipedia.org/wiki/Magnet_URI_scheme
MAGNET_LINK_REGEX = re.compile(
    r"(magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:&(?:xt|dn|xl|tr|ws|as|xs|kt|mt|so|x\.pe)=[^\s]+)*)"
)

CLIENT_ID_REGEX = re.compile(r"^[a-zA-Z\-\_0-9]+$")









