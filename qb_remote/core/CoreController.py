from logging import warn
import sys, os
import json
import traceback
import time
import threading
import collections
import random
from typing import Callable


import qbittorrentapi
from qbittorrentapi import SyncMainDataDictionary

from . import CoreGlobals as CG
from . import CoreExceptions as CE
from . import CoreData as CD
from . import CoreConstants as CC
from . import CoreCaches as Cache
from . import CoreLogging as logging
from . import CoreThreading


class ClientController(object):
    def __init__(self):
        CG.controller = self

        self._name: str = CC.BRAND

        self._daemon_jobs: dict[str, CoreThreading.Schedulable_Job] = {}
        self._caches: dict[str, Cache.Data_Cache] = {}
        self._expiring_caches: dict[str, Cache.Expiring_Data_Cache] = {}

        self._call_to_threads: list[CoreThreading.Thread_Call_To_Thread] = []

        self.torrent_files_cache = Cache.Expiring_Data_Cache(
            "torrent_files_cache", CC.TORRENT_CACHE_TIME_SECONDS
        )
        self.torrent_metadata_cache = Cache.Data_Cache("torrent_files_cache")
        self.file_priority_transaction_cache = Cache.Data_Cache("torrent_files_cache")
        self.syncronized_torrent_metadata_cache = Cache.Data_Cache(
            "syncronized_torrent_files_cache"
        )
        self.client_cache = Cache.Data_Cache("client_cache")
        self._caches["client_cache"] = self.client_cache
        self._caches["torrent_files_cache"] = self.torrent_files_cache
        self._caches["torrent_metadata_cache"] = self.torrent_metadata_cache
        self._caches["file_priority_transaction_cache"] = self.file_priority_transaction_cache
        self._caches["syncronized_torrent_metadata_cache"] = self.syncronized_torrent_metadata_cache

        self._fast_job_scheduler:CoreThreading.Job_Scheduler = None
        self._slow_job_scheduler:CoreThreading.Job_Scheduler = None

        self._call_to_thread_lock = threading.Lock()

        self._timestamps_lock = threading.Lock()

        self._timestamps: collections.defaultdict[str, int] = collections.defaultdict(lambda: 0)

        self._timestamps["boot"] = CD.time_now()

        self._timestamps["last_sleep_check"] = CD.time_now()

        self._timestamps["commit_torrent_priority_update"] = CD.time_now()

        self._sleep_lock = threading.Lock()

        self._just_woke_from_sleep = False

        self._system_busy = False

        self._doing_fast_exit = False

        self.client_id = None


        self.qbittorrent: qbittorrentapi.Client = qbittorrentapi.Client()
        self.qbittorrent_initialized : bool = False
        self.settings   = {
                "qbit" : {
                    "host" : "127.0.0.1",
                    "port" : 8080,
                    "username" : "root",
                    "password" : "root",
                    "autoconnect" : True ,
                    "reconnect_on_update" : True 
                    }
                }


    def _get_wake_delay_period(self):
        return 15

    def _show_just_woke_to_user(self):
        logging.info("Just woke from sleep.")

    def _get_appropriate_job_scheduler(self, time_delta):
        if time_delta <= 1.0:
            return self._fast_job_scheduler

        else:
            return self._slow_job_scheduler

    def _shutdown_daemons(self):
        for job in self._daemon_jobs.values():
            job.cancel()

        started = CD.time_now()

        while True in (
            daemon_job.is_currently_working() for daemon_job in self._daemon_jobs.values()
        ):
            time.sleep(0.1)

            if CD.time_has_passed(started + 30):
                break

        self._daemon_jobs = {}

    def _get_call_to_thread(self):
        with self._call_to_thread_lock:
            for call_to_thread in self._call_to_threads:
                if not call_to_thread.is_currently_working():
                    return call_to_thread

            # all the threads in the pool are currently busy

            calling_from_the_thread_pool = threading.current_thread() in self._call_to_threads

            if calling_from_the_thread_pool or len(self._call_to_threads) < 200:
                call_to_thread = CoreThreading.Thread_Call_To_Thread(self, "CallToThread")

                self._call_to_threads.append(call_to_thread)

                call_to_thread.start()

            else:
                call_to_thread = random.choice(self._call_to_threads)

            return call_to_thread

    def call_to_thread(self, callable: Callable, *args, **kwargs):
        call_to_thread = self._get_call_to_thread()

        call_to_thread.put(callable, *args, **kwargs)

    def call_later(
        self, initial_delay_seconds: float, func: Callable, *args, **kwargs
    ) -> CoreThreading.Single_Job:
        job_scheduler = self._get_appropriate_job_scheduler(initial_delay_seconds)

        call = CD.Call(func, *args, **kwargs)

        job = CoreThreading.Single_Job(self, job_scheduler, initial_delay_seconds, call)

        job_scheduler.add_job(job)

        return job

    def call_repeating(
        self, initial_delay_seconds: float, period: float, func: Callable, *args, **kwargs
    ) -> CoreThreading.Repeating_Job:
        job_scheduler = self._get_appropriate_job_scheduler(period)

        call = CD.Call(func, *args, **kwargs)

        job = CoreThreading.Repeating_Job(self, job_scheduler, initial_delay_seconds, period, call)

        job_scheduler.add_job(job)

        return job

    def clear_caches(self):
        for cache in list(self._caches.values()):
            cache.clear()

    def is_doing_fast_exit(self) -> bool:
        return self._doing_fast_exit

    def is_good_time_to_start_background_work(self):
        return not (self.just_woke_from_sleep() or self.is_system_busy())

    def is_good_time_to_start_foreground_work(self):
        return not self.just_woke_from_sleep()

    def is_system_busy(self):
        return self._system_busy

    def just_woke_from_sleep(self):
        self.sleep_check()

        return self._just_woke_from_sleep

    def get_boot_time(self):
        return self.get_timestamp("boot")

    def get_cache(self, name):
        return self._caches[name]

    def get_timestamp(self, name: str) -> int:
        with self._timestamps_lock:
            return self._timestamps[name]

    def init_model(self):
        self._fast_job_scheduler = CoreThreading.Job_Scheduler(self)
        self._slow_job_scheduler = CoreThreading.Job_Scheduler(self)

        self._fast_job_scheduler.start()
        self._slow_job_scheduler.start()

    def init_view(self):
        job = self.call_repeating(0.0, 15.0, self.sleep_check)
        self._daemon_jobs["sleep_check"] = job

        job = self.call_repeating(10.0, 60.0, self.maintain_memory_fast)
        self._daemon_jobs["maintain_memory_fast"] = job

    def maintain_memory_fast(self):
        sys.stdout.flush()
        sys.stderr.flush()

        self._fast_job_scheduler.clear_out_dead()
        self._slow_job_scheduler.clear_out_dead()

    def reset_idle_timer(self):
        self.touch_timestamp("last_user_action")

    def set_doing_fast_exit(self, value: bool):
        self._doing_fast_exit = value

    def set_timestamp(self, name: str, value: int):
        with self._timestamps_lock:
            self._timestamps[name] = value

    def set_qbittorrent_setting(self, key:str, value):

        self.settings['qbit'][key] = value


    def get_qbittorrent_setting(self, key:str):
        return self.settings['qbit'].get(key, None)

    def shutdown_model(self):
        if self._fast_job_scheduler is not None:
            self._fast_job_scheduler.shutdown()

            self._fast_job_scheduler = None

        if self._slow_job_scheduler is not None:
            self._slow_job_scheduler.shutdown()

            self._slow_job_scheduler = None

        with self._call_to_thread_lock:
            for call_to_thread in self._call_to_threads:
                call_to_thread.shutdown()

            # for long_running_call_to_thread in self._long_running_call_to_threads:

            #     long_running_call_to_thread.shutdown()

        CG.model_shutdown = True

    def shutdown_view(self):
        CG.view_shutdown = True

        self._shutdown_daemons()

    def sleep_check(self):
        with self._sleep_lock:
            logging.debug("Sleep check")

            # it has been way too long since this method last fired, so we've prob been asleep
            if CD.time_has_passed(self.get_timestamp("last_sleep_check") + 60):
                self._just_woke_from_sleep = True

                # this will stop the background jobs from kicking in as soon as the grace period is over
                self.reset_idle_timer()

                wake_delay_period = self._get_wake_delay_period()

                # enough time for ethernet to get back online and all that
                self.set_timestamp("now_awake", CD.time_now() + wake_delay_period)

                self._show_just_woke_to_user()

            elif self._just_woke_from_sleep and CD.time_has_passed(self.get_timestamp("now_awake")):
                self._just_woke_from_sleep = False

            self.touch_timestamp("last_sleep_check")

    def simulate_wake_from_sleep_event(self):
        with self._sleep_lock:
            self.set_timestamp("last_sleep_check", CD.time_now() - 3600)

        self.sleep_check()

    def touch_timestamp(self, name: str):
        with self._timestamps_lock:
            self._timestamps[name] = CD.time_now()

    def wake_daemon(self, name):
        if name in self._daemon_jobs:
            self._daemon_jobs[name].wake()

    def is_qbittorrent_ok(self):
        return self.qbittorrent_initialized

    def init_qbittorrent_connection(self):

        if self.qbittorrent_initialized:
            self.shutdown_qbittorrent_connection()

        self.qbittorrent._password = self.settings['qbit']['password'] 
        self.qbittorrent.username = self.settings['qbit']['username'] 
        self.qbittorrent.host = self.settings['qbit']['host'] 
        self.qbittorrent.port = self.settings['qbit']['port'] 

        try:
            self.qbittorrent.auth_log_in(timeout=5)
            logging.info(CD.get_client_build_information(self.qbittorrent))
            self.qbittorrent_initialized = True
        except qbittorrentapi.LoginFailed as e:
            logging.warn(e)
        except qbittorrentapi.APIConnectionError as e:
            logging.error(e)



    def shutdown_qbittorrent_connection(self):


        self.qbittorrent.auth_log_out()
        self.qbittorrent_initialized = False


    def boot_everything_base(self):
        # try:

        #     self.CheckAlreadyRunning()

        # except NyanExceptions.Shutdown_Exception:

        #     logging.warning("Already running this controller instance!")
        #     return

        try:
            self.init_model()

            self.init_view()

            if CC.IS_PROFILE_MODE:
                self.create_client_tag()

            self._is_booted = True

            CD.load_settings(self.settings)

            if self.get_qbittorrent_setting("autoconnect"):
            self.init_qbittorrent_connection()

        except CE.Shutdown_Exception as e:
            logging.error(e)

        except Exception as e:
            trace = traceback.format_exc()

            logging.error(trace)

    def exit_everything_base(self):
        try:
            CG.started_shutdown = True

            try:
                self.shutdown_qbittorrent_connection()
            except:
                pass

            try:
                CD.save_settings(self.settings)
            except Exception as e:
                logging.error(e)

            self.shutdown_view()

            self.shutdown_model()

        except CE.Shutdown_Exception:
            pass

        except Exception as e:
            logging.error(traceback.format_exc())

        finally:
            self._program_is_shut_down = True

    ### Torrent Stuff

    def sync_get_metadata(self):

        if not self.qbittorrent_initialized:
            return
        cache = self.get_cache("syncronized_torrent_metadata_cache")

        with cache.get_lock():
            synced_meta: SyncMainDataDictionary |None= cache.get_if_has_data_unsafe(
                "syncronized_metadata"
            )

            if not synced_meta:
                synced_meta = self.qbittorrent.sync.maindata.delta()

                cache.add_data_unsafe("syncronized_metadata", synced_meta, True)

                return synced_meta

            else:
                updated_metadata = self.qbittorrent.sync.maindata.delta()
                CD.update_dictionary_no_key_remove(synced_meta, updated_metadata)

                return updated_metadata

    def get_metadata_delta(self):
        if not self.qbittorrent_initialized:
            return
        updated_metadata = self.qbittorrent.sync.maindata.delta()

        return updated_metadata

    def get_torrents(self, skip_cache=False, **kwargs):
        """
        Gets all torrent files, either from a cache or fresh,

        Cache expires ever 120 seconds
        """
        if not self.qbittorrent_initialized:
            return

        if not skip_cache and not kwargs:
            data = self.torrent_files_cache.get_if_has_non_expired_data("torrent_list")

            if data:
                logging.debug("Cache hit for 'torrent_list'")
                return data
            else:
                logging.debug("Cache miss for 'torrent_list'")

            data = self.qbittorrent.torrents_info(**kwargs)

            self.torrent_files_cache.add_data("torrent_list", data, True)

            return data

        logging.debug(
            f"Custom call to torrent_info, skipping cache. kwargs = {kwargs}, skip_cache = {skip_cache}"
        )

        return self.qbittorrent.torrents_info(**kwargs)

    def update_torrents_file_priority_transactional(
        self, torret_hash: str, file_id: int, priority: int
    ):
        """
        Updates the torrents files priority after 2 seconds,

        All function calls for the given torrent in that time will be added to the transaction,

        After the 2 seconds all the files will be updated to reflect the final state of the transaction
        """
        if not self.qbittorrent_initialized:
            return

        if not self.file_priority_transaction_cache.has_data(torret_hash):
            self.file_priority_transaction_cache.add_data(
                torret_hash, {"file_ids": [file_id], "priority": priority}, True
            )

            def callback(torrent_hash):
                c = self.get_cache("file_priority_transaction_cache")

                data = c.get_if_has_data(torrent_hash, True)

                if not data:
                    return

                logging.info(f"Updating torrent priority for {torrent_hash}")

                self.qbittorrent.torrents_file_priority(
                    torrent_hash, data["file_ids"], data["priority"]
                )

            self.call_later(2, callback, torret_hash)

        else:
            self.file_priority_transaction_cache.get_data(torret_hash)["file_ids"].append(file_id)

    def upload_torrents(self, magnet_links_and_info: dict[str]):
        if not self.qbittorrent_initialized:
            return
        try:

            if CC.IS_PROFILE_MODE:
                tags = magnet_links_and_info.get('tags', None)

                if tags is None:
                    magnet_links_and_info['tags'] = [self.get_client_id()]
                else:
                    tags.append(self.get_client_id())


            e = self.qbittorrent.torrents_add(**magnet_links_and_info)

        except Exception as e:
            logging.error(e)

    def get_client_preferences(self, skip_cache=False):
        if not self.qbittorrent_initialized:
            return
        TIMESTAMP = "update_pref_cache"
        CACHE_KEY = "app_preferences"

        self.get_client_categories()

        if skip_cache or CD.time_has_passed(self.get_timestamp(TIMESTAMP) + 60):
            self.touch_timestamp(TIMESTAMP)

            a = self.qbittorrent.app_preferences()

            self.client_cache.add_data(CACHE_KEY, a, True)
            return a

        return self.client_cache.get_if_has_data(CACHE_KEY)

    def get_client_categories(self, skip_cache=False):
        if not self.qbittorrent_initialized:
            return
        TIMESTAMP = "update_cat_cache"
        CACHE_KEY = "torrent_categories"

        if skip_cache or CD.time_has_passed(self.get_timestamp(TIMESTAMP) + 30):
            self.touch_timestamp(TIMESTAMP)

            a = self.qbittorrent.torrents_categories()

            self.client_cache.add_data(CACHE_KEY, a, True)
            return a

        return self.client_cache.get_if_has_data(CACHE_KEY)


    def get_client_id(self, include_prefix:bool = True):
        self.create_client_tag()

        _ = CC.DEFAULT_CLIENT_ID

        if not self.client_id:
            if not include_prefix:
                return _
            return 'user_' + _

        _ = self.client_id

        if not include_prefix:
            return _
        return 'user_' + _

    def change_client_id(self, new_client_id: str):

        if new_client_id is None or CC.USE_HARDWARE_ID:
            return

        new_client_id = new_client_id[0:64].strip()

        if not CC.CLIENT_ID_REGEX.match(new_client_id):
            logging.warning(f"Trying to change client_id to invalid value of: {new_client_id}")
            return 

        self.client_id = new_client_id

        CD.save_guid(new_client_id)

        if CC.IS_PROFILE_MODE:
            self.qbittorrent.torrents_create_tags([self.get_client_id()])

    def create_client_tag(self):

        if not self.qbittorrent_initialized:
            return
        client_tag =  CD.get_guid()

        if not self.client_id:
            self.client_id = client_tag

        logging.info(f"Client ID: {client_tag}")

        if CC.IS_PROFILE_MODE:
            self.qbittorrent.torrents_create_tags(['user_' + client_tag])


    def torrent_passes_filter(self, torrent_dict: dict):

        passes = True

        if CC.IS_PROFILE_MODE:
            self.create_client_tag()

            tags = torrent_dict.get('tags', None)

            if tags:

                tags = set(tags.split(", "))

                if self.get_client_id() not in tags:
                    passes = False

            else:
                passes = False

        return passes
