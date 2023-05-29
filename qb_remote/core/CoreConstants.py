
import datetime
import time
import sys
import os

START_TIME_PRECISE = time.perf_counter()
# ha, subtracting here makes it suuuper close the psutil.create_time()
START_TIME_FLOAT = time.time() - START_TIME_PRECISE
START_TIME = int(START_TIME_FLOAT)

START_TIME_DATE = datetime.datetime.now()
START_TIME_PRETTY = datetime.datetime.strftime(START_TIME_DATE, "%Y-%m-%d %H:%M:%S")

BRAND = "qBittorrent Remote GUI"

TORRENT_CACHE_TIME_SECONDS = 120
