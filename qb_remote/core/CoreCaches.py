
import time
import sys
import traceback
import os
import json
import threading
import collections
from typing import Union, Callable, TYPE_CHECKING

from . import CoreData as CD
from . import CoreExceptions as CE

class Data_Cache(object):
    def __init__(self,  name: str, timeout: int = 1200):

        self._name: str = name
        self._timeout: int = timeout

        self._keys_to_data: dict[str] = {}
        self._keys_fifo: dict[str, int] = collections.OrderedDict()

        self._lock = threading.Lock()


    def _delete(self, key: str):

        if key not in self._keys_to_data:
            return

        del self._keys_to_data[key]

    def _delete_item(self):

        (delete_key, last_access_time) = self._keys_fifo.popitem(last=False)

        self._delete(delete_key)

    def _touch_key(self, key):

        # have to delete first, rather than overwriting, so the ordereddict updates its internal order
        if key in self._keys_fifo:

            del self._keys_fifo[key]

        self._keys_fifo[key] = CD.time_now()

    def clear(self):

        with self._lock:

            self._keys_to_data = {}
            self._keys_fifo = collections.OrderedDict()

    def add_data(self, key, data, replace=False):

        with self._lock:

            if key in self._keys_to_data and not replace:
                return

            self._keys_to_data[key] = data

            self._touch_key(key)

    def delete_data(self, key):

        with self._lock:

            self._delete(key)

    def get_data(self, key):

        with self._lock:

            if key not in self._keys_to_data:

                raise CE.Cache_Lookup_Exception(f"Cache error! Looking for {key}, but it was missing.")

            self._touch_key(key)

            return self._keys_to_data[key]

    def get_if_has_data(self, key):

        with self._lock:

            if key in self._keys_to_data:

                self._touch_key(key)

                return self._keys_to_data[key]

            return None

    def has_data(self, key):

        with self._lock:

            return key in self._keys_to_data

    def maintain_cache(self):

        with self._lock:

            while True:

                if len(self._keys_fifo) == 0:

                    return

                (key, last_access_time) = next(iter(self._keys_fifo.items()))

                if CD.time_has_passed(last_access_time + self._timeout):

                    self._delete_item()

                else:

                    break

    def set_timeout(self, timeout: int):

        with self._lock:

            self._timeout = timeout

        self.maintain_cache()


class Expiring_Data_Cache(Data_Cache):
    def __init__(self, name: str, timeout: int = 1200):
        Data_Cache.__init__(self, name, timeout)

    def get_data(self, key):

        with self._lock:

            if key not in self._keys_to_data:

                raise CE.Cache_Lookup_Exception(f"Cache error! Looking for {key}, but it was missing.")

            data_added_time = self._keys_fifo[key]

            if CD.time_has_passed(data_added_time + self._timeout):

                raise CE.Cache_Expired_Exception(f"Cache error! Data for {key} has expired.")

            return self._keys_to_data[key]

    def get_if_has_data(self, key):

        with self._lock:

            if key in self._keys_to_data:

                data_added_time = self._keys_fifo[key]

                if CD.time_has_passed(data_added_time + self._timeout):

                    raise CE.Cache_Expired_Exception(f"Cache error! Data for {key} has expired.")

                return self._keys_to_data[key]

            return None

    def get_if_has_non_expired_data(self, key):

        with self._lock:

            if key in self._keys_to_data:

                data_added_time = self._keys_fifo[key]

                if CD.time_has_passed(data_added_time + self._timeout):

                    return None

                return self._keys_to_data[key]

            return None

    def has_non_expired_data(self, key):

        with self._lock:

            return key in self._keys_to_data and not CD.time_has_passed(self._keys_fifo[key] + self._timeout)
