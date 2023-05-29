import math
import os 
import time
from typing import Union, Callable, TYPE_CHECKING

from qbittorrentapi import TorrentFilesList

from . import CoreGlobals as CG
from . import CoreConstants as CC


try:
    import psutil

    PSUTIL_OK = True

except ImportError:

    PSUTIL_OK = False


def get_client_build_information():
    if not CG.client_initialized:
        raise RuntimeError("qBittorrent not initialized!")

    return "\n".join(
        (
            f"qBittorrent: {CG.client_instance.app.version}",
            f"qBittorrent Web API: {CG.client_instance.app.web_api_version}",
            "\n".join(f"{k}: {v}" for k, v in CG.client_instance.app.build_info.items()),
        )
    )


def size_bytes_to_pretty_str(size_bytes: int):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


def get_pretty_download_priority(priority):
    if priority == 0:
        return "Do Not Download"

    if priority == 1:
        return "Normal"

    if priority == 6:
        return "High"

    if priority == 7:
        return "Maximum"

    return "Unknown"



def get_create_time():

    if CC.PSUTIL_OK:
        try:

            me = psutil.Process()

            return me.create_time()

        except psutil.Error:

            pass

    return CC.START_TIME


def get_up_time():

    return time.time() - get_create_time()


def time_now() -> int:

    return int(time.time())


def time_now_float() -> float:

    return time.time()


def time_now_precise() -> float:

    return time.perf_counter()


def time_has_passed(timestamp: Union[float, int]) -> bool:

    if timestamp is None:

        return False

    return time_now() > timestamp


def time_has_passed_float(timestamp: Union[float, int]) -> bool:

    return time_now_float() > timestamp


def time_has_passed_precise(precise_timestamp: Union[float, int]) -> bool:

    return time_now_precise() > precise_timestamp


def time_until(timestamp: Union[float, int]) -> Union[float, int]:

    return timestamp - time_now()


def time_delta_since_time(timestamp):

    time_since = timestamp - time_now()

    result = min(time_since, 0)

    return -result


def time_delta_until_time(timestamp):

    time_remaining = timestamp - time_now()

    return max(time_remaining, 0)


def time_delta_until_time_float(timestamp):

    time_remaining = timestamp - time_now_float()

    return max(time_remaining, 0.0)


def time_delta_until_time_precise(t):

    time_remaining = t - time_now_precise()

    return max(time_remaining, 0.0)


def hours_to_seconds(time_hours: float):

    return time_hours * 60 * 60


class NestedTorrentFileDirectory:

    def __init__(self, name, size=0) -> None:
        self.name = name
        self.torrent = None
        self.size = size
        self.children = {}
        
    def sum_size(self):

        for child in self.children:
            self.size += child.sum_size()
        
        return self.size

def build_nested_torrent_structure(torrent_files: TorrentFilesList):
   
    root = NestedTorrentFileDirectory("/")
   
    for file in torrent_files:

        components = file['name'].split(os.sep)

        dir = None
        current = root.children
        for component in components:
            dir = NestedTorrentFileDirectory(component)
            current = current.setdefault(component, dir)
            current.size += file['size']
            current = current.children
        
        if dir:
            dir.torrent = file 

    return root
   
   