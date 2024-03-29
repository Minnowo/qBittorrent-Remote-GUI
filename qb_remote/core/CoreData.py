import json
import math
import subprocess
import sys
import os
import hashlib
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


def get_client_build_information(qbittorrent):

    return "\n".join(
        (
            f"qBittorrent: {qbittorrent.app.version}",
            f"qBittorrent Web API: {qbittorrent.app.web_api_version}",
            "\n".join(f"{k}: {v}" for k, v in qbittorrent.app.build_info.items()),
        )
    )


def size_bytes_to_pretty_str(size_bytes: int):
    if size_bytes == 0:
        return "0B"
    
    is_negative = False
    if size_bytes < 0:
        size_bytes *= -1
        is_negative = True

    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)

    if is_negative:
        s *= -1
    return "%s %s" % (s, size_name[i])


def get_pretty_download_priority(priority):
    if priority == CC.TORRENT_FILE_PRIORITY_DO_NOT_DOWNLOAD:
        return "Do Not Download"

    if priority == CC.TORRENT_FILE_PRIORITY_NORMAL:
        return "Normal"

    if priority == CC.TORRENT_FILE_PRIORITY_HIGH:
        return "High"

    if priority == CC.TORRENT_FILE_PRIORITY_MAXIMUM:
        return "Maximum"

    return "Unknown"


def torrent_state_to_pretty(state_: str):
    state = state_.lower()

    if state == "stalledup":
        return "Seeding"

    if state == "stalled" or state == "stalleddown":
        return "Stalled"

    if state == "downloading":
        return "Downloading"

    if state == "pauseddl":
        return "Paused"

    if state == "uploading":
        return "Uploading"

    return state_


from typing import MutableMapping


def update_dictionary_no_key_remove(dicta: MutableMapping, dictb: MutableMapping):
    for key, value in dictb.items():
        if key in dicta and isinstance(dicta[key], MutableMapping) and isinstance(value, dict):
            update_dictionary_no_key_remove(dicta[key], value)
        else:
            dicta[key] = value


def get_create_time():
    if PSUTIL_OK:
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


def to_human_int(num):
    num = int(num)

    text = "{:,}".format(num)

    return text


def time_delta_to_pretty_time_delta(seconds, show_seconds=True):
    if seconds is None:
        return "per month"

    if seconds == 0:
        return "0 seconds"

    if seconds < 0:
        seconds = abs(seconds)

    if seconds >= 60:
        seconds = int(seconds)

        MINUTE = 60
        HOUR = 60 * MINUTE
        DAY = 24 * HOUR
        MONTH = 30 * DAY
        YEAR = 365 * DAY

        lines = [
            ("year", YEAR),
            ("month", MONTH),
            ("day", DAY),
            ("hour", HOUR),
            ("minute", MINUTE),
        ]

        if show_seconds:
            lines.append(("second", 1))

        result_components = []

        for time_string, duration in lines:
            time_quantity = seconds // duration

            seconds %= duration

            # little rounding thing if you get 364th day with 30 day months
            if time_string == "month" and time_quantity > 11:
                time_quantity = 11

            if time_quantity > 0:
                s = to_human_int(time_quantity) + " " + time_string

                if time_quantity > 1:
                    s += "s"

                result_components.append(s)

                if len(result_components) == 2:  # we now have 1 month 2 days
                    break

            else:
                # something like '1 year' -- in which case we do not care about the days and hours
                if len(result_components) > 0:
                    break

        return " ".join(result_components)

    if seconds > 1:
        if int(seconds) == seconds:
            return to_human_int(seconds) + " seconds"

        return "{:.1f} seconds".format(seconds)

    if seconds == 1:
        return "1 second"

    if seconds > 0.1:
        return "{} milliseconds".format(int(seconds * 1000))

    if seconds > 0.01:
        return "{:.1f} milliseconds".format(int(seconds * 1000))

    if seconds > 0.001:
        return "{:.2f} milliseconds".format(int(seconds * 1000))

    return "{} microseconds".format(int(seconds * 1000000))


class NestedTorrentFileDirectory:
    def __init__(self, name, size=0) -> None:
        self.name = name
        self.torrents_file = None
        self.size = size
        self.progress = 0
        self.children: dict[str, NestedTorrentFileDirectory] = {}

    def recalculate_size(self):
        if self.torrents_file:
            self.size = self.torrents_file.size
        else:
            self.size = 0

        self.size += sum(d.recalculate_size() for d in self.children.values())

        return self.size

    def _get_progress(self):
        return self.progress * self.size + sum(d._get_progress() for d in self.children.values())

    def get_progress(self):
        p = self._get_progress()

        if self.size == 0:
            return -1

        return p / self.size


def build_nested_torrent_structure(torrent_files: TorrentFilesList):
    root = NestedTorrentFileDirectory("/")

    for file in torrent_files:
        components = file.name.split(os.sep)

        dir = None
        current = root.children
        for component in components:
            dir = NestedTorrentFileDirectory(component)
            current = current.setdefault(component, dir)
            current.size += file.size
            current = current.children

        if dir:
            dir.torrents_file = file
            dir.progress = file.progress

    return root


class Call(object):
    def __init__(self, func: Callable, *args, **kwargs):
        self._label = None

        self._func = func
        self._args = args
        self._kwargs = kwargs

    def __call__(self):
        self._func(*self._args, **self._kwargs)

    def __repr__(self):
        label = self._GetLabel()

        return "Call: {}".format(label)

    def _GetLabel(self) -> str:
        if self._label is None:
            # this can actually cause an error with Qt objects that are dead or from the wrong thread, wew!
            label = "{}( {}, {} )".format(self._func, self._args, self._kwargs)

        else:
            label = self._label

        return label

    def GetLabel(self) -> str:
        return self._GetLabel()

    def SetLabel(self, label: str):
        self._label = label

def save_settings(settings:dict):

    os.makedirs(CC.CONFIG_DIRECTORY, exist_ok=True)

    with open(CC.CONFIG_CLIENT_SETTINGS, "w") as writer:
       json.dump(settings, writer, indent=3) 

def load_settings(settings:dict):

    if not os.path.isfile(CC.CONFIG_CLIENT_SETTINGS):
        return

    with open(CC.CONFIG_CLIENT_SETTINGS, "r") as reader:
        data = json.load(reader)

        update_dictionary_no_key_remove(settings, data)

def save_guid(guid:str):
    if guid is None:
        return

    os.makedirs(CC.CONFIG_DIRECTORY, exist_ok=True)

    with open(CC.CONFIG_CLIENT_ID_FILE, "w") as writer:
        writer.write(guid[0:64].strip())

def get_guid():

    if CC.USE_HARDWARE_ID:
        _ = get_machine_guid()

        if _ is not None:

            hash = hashlib.sha1()
            hash.update(_.encode())
            hash.update(sys.platform.encode())
            return hash.digest().hex()
        
        raise Exception("Cannot generate hardware id")

    if os.path.isfile(CC.CONFIG_CLIENT_ID_FILE):
        with open(CC.CONFIG_CLIENT_ID_FILE, "r") as reader:
            return reader.read(64).strip()

    return "UNKNOWN"
    

def run(cmd):
  try:
    return subprocess.run(cmd, shell=True, capture_output=True, check=True, encoding="utf-8") \
                     .stdout \
                     .strip()
  except:
    return None

def get_machine_guid():
  if sys.platform == 'darwin':
    return run(
      "ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" '/IOPlatformUUID/{print $(NF-1)}'",
    )

  if sys.platform == 'win32' or sys.platform == 'cygwin' or sys.platform == 'msys':
    return run('wmic csproduct get uuid').split('\n')[2] \
                                         .strip()

  if sys.platform.startswith('linux'):
    return run('cat /var/lib/dbus/machine-id') or \
           run('cat /etc/machine-id')

  if sys.platform.startswith('openbsd') or sys.platform.startswith('freebsd'):
    return run('cat /etc/hostid') or \
           run('kenv -q smbios.system.uuid')



def join_path_remote(remote: str, *args):

    # always using / because it *should* work fine on both windows and unix-like
    sep = "/"

    # always assume the remote path is correct other than this
    remote = remote.replace("\\", sep)

    if not args:
        return remote 

    args = sep.join(
            sep.join(
                filter(
                    lambda x : not not x.strip(), 
                    s.replace("\\", sep).split(sep)
                )
            ) for s in args
        )

    return sep.join([remote, args])
