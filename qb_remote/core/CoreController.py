import sys, os
import logging
import json
import traceback
import time
import threading
import collections
import random
from typing import Callable


import qbittorrentapi
from qbittorrentapi import SyncMainDataDictionary
from qbittorrentapi.exceptions import NotFound404Error

from . import CoreGlobals as CG
from . import CoreExceptions as CE
from . import CoreData as CD
from . import CoreConstants as CC
from . import CoreCaches as Cache
from . import CoreThreading

class ClientControllerUser():

    CONTROLLER:"ClientController" = None

class ClientController(ClientControllerUser):
    def __init__(self):

        ClientControllerUser.CONTROLLER = self

        self._name: str = CC.BRAND

        self._daemon_jobs: dict[str, CoreThreading.Schedulable_Job] = {}
        self._caches:list[Cache.Data_Cache] = [] 
        self._expiring_caches:list[Cache.Expiring_Data_Cache] = [] 

        self._call_to_threads: list[CoreThreading.Thread_Call_To_Thread] = []


        self.qbittorrent_cache = Cache.Data_Cache("qbittorrent")
        self._caches.append(self.qbittorrent_cache)

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
        self.qbittorrent_lock :threading.Lock = threading.Lock()
        self.settings   = {
                "qbit" : {
                    "host" : "127.0.0.1",
                    "port" : 8080,
                    "username" : "root",
                    "password" : "root",
                    "autoconnect" : True ,
                    "reconnect_on_update" : True ,
                    },
                "categories_to_hide": []
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

    def get_timestamp(self, name: str) -> int:
        with self._timestamps_lock:
            return self._timestamps[name]

    def init_model(self):
        self._fast_job_scheduler = CoreThreading.Job_Scheduler(self)
        self._slow_job_scheduler = CoreThreading.Job_Scheduler(self)

        self._fast_job_scheduler.start()
        self._slow_job_scheduler.start()

    def init_view(self):
        job = self.call_repeating(10.0, 5*60.0, self.maintain_memory_fast)
        self._daemon_jobs["maintain_memory_fast"] = job

        job = self.call_later(10, self.post_boot)

    def maintain_memory_fast(self):

        logging.info("Maintaining memory")

        if sys.stdout:
            sys.stdout.flush()
        if sys.stderr:
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
            logging.info("Sleep check")

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

        with self.qbittorrent_lock:

            self.qbittorrent._password = self.settings['qbit']['password'] 
            self.qbittorrent.username = self.settings['qbit']['username'] 
            self.qbittorrent.host = self.settings['qbit']['host'] 
            self.qbittorrent.port = self.settings['qbit']['port'] 

            try:
                logging.info(f"Trying to connect to qBittorrent at {self.qbittorrent.host}:{self.qbittorrent.port}")
                self.qbittorrent.auth_log_in()
                logging.info(CD.get_client_build_information(self.qbittorrent))
                self.qbittorrent_initialized = True
            except qbittorrentapi.LoginFailed as e:
                logging.warn(e)
            except qbittorrentapi.APIConnectionError as e:
                logging.error(e)



    def shutdown_qbittorrent_connection(self):

        with self.qbittorrent_lock:

            self.qbittorrent.auth_log_out()
            self.qbittorrent_initialized = False

    def post_boot(self):

        if self.get_qbittorrent_setting("autoconnect"):
            self.init_qbittorrent_connection()

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


    def get_metadata_delta(self):
        if not self.qbittorrent_initialized:
            return
        updated_metadata = self.qbittorrent.sync.maindata.delta()

        return updated_metadata


    def get_torrents_files(self, torrent_hash : str):
        if not self.qbittorrent_initialized:
            return

        CACHE_KEY = f"torrent_files_{torrent_hash}"
        CACHE = self.qbittorrent_cache

        data = CACHE.get_if_has_data(CACHE_KEY)

        if data:
            logging.debug(f"Cache hit for torrent hash: {torrent_hash}")
            return data

        try:
            data = self.CONTROLLER.qbittorrent.torrents_files(torrent_hash)

            CACHE.add_data(CACHE_KEY, data, True)

            return data

        except NotFound404Error:
            logging.warning(f"Could not find torrent with hash: {torrent_hash}")



    def get_torrents(self, skip_cache=False, cache_key=None, **kwargs):
        """
        Gets all torrent files, either from a cache or fresh,

        Cache expires ever 120 seconds
        """
        if not self.qbittorrent_initialized:
            return

        if skip_cache or (kwargs and cache_key is None):

            logging.debug(
                f"Custom call to torrent_info, skipping cache. kwargs = {kwargs}, skip_cache = {skip_cache}"
            )

            return self.qbittorrent.torrents_info(**kwargs)

        CACHE = self.qbittorrent_cache
        CACHE_KEY = cache_key or "torrents"
        TIMESTAMP = "torrents_cache"

        data = CACHE.get_if_has_data(CACHE_KEY)

        if not data or CD.time_has_passed(self.get_timestamp(TIMESTAMP) + 60):

            data = self.qbittorrent.torrents_info()

            CACHE.add_data(CACHE_KEY, data, True)

        return data

    def update_torrents_file_priority_transactional(
        self, torrent_hash: str, file_id: int, priority: int
    ):
        """
        Updates the torrents files priority after 2 seconds,

        All function calls for the given torrent in that time will be added to the transaction,

        After the 2 seconds all the files will be updated to reflect the final state of the transaction
        """
        if not self.qbittorrent_initialized:
            return

        CACHE_KEY = f"file_priority_transaction_{torrent_hash}"
        CACHE = self.qbittorrent_cache


        if CACHE.has_data(CACHE_KEY):
            CACHE.get_data(CACHE_KEY)["file_ids"].append(file_id)
            return


        CACHE.add_data(
            CACHE_KEY, {"file_ids": [file_id], "priority": priority}, True
        )

        def callback(cache_key, torrent_hash):

            data = CACHE.get_if_has_data(cache_key, True)

            if not data:
                return

            logging.info(f"Updating torrent priority for {torrent_hash}")

            self.qbittorrent.torrents_file_priority(
                torrent_hash, data["file_ids"], data["priority"]
            )

        self.call_later(2, callback, CACHE_KEY, torrent_hash)

    def set_torrents_paused(self, torrent_hash: list[str]):

        if not self.qbittorrent_initialized:
            return

        self.qbittorrent.torrents_pause(torrent_hash)

    def set_torrents_resume(self, torrent_hash: list[str]):

        if not self.qbittorrent_initialized:
            return

        self.qbittorrent.torrents_resume(torrent_hash)

    def upload_torrents(self, magnet_links_and_info: dict[str]):
        if not self.qbittorrent_initialized:
            return
        try:

            if CC.IS_PROFILE_MODE:
                self.create_client_tag()
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
        CACHE = self.qbittorrent_cache

        self.get_client_categories()

        if skip_cache or CD.time_has_passed(self.get_timestamp(TIMESTAMP) + 60):
            self.touch_timestamp(TIMESTAMP)

            a = self.qbittorrent.app_preferences()

            CACHE.add_data(CACHE_KEY, a, True)
            return a

        return CACHE.get_if_has_data(CACHE_KEY)

    def get_client_categories(self, skip_cache=False):
        if not self.qbittorrent_initialized:
            return

        TIMESTAMP = "update_cat_cache"
        CACHE_KEY = "torrent_categories"

        if skip_cache or CD.time_has_passed(self.get_timestamp(TIMESTAMP) + 30):
            self.touch_timestamp(TIMESTAMP)

            a = self.qbittorrent.torrents_categories()

            self.qbittorrent_cache.add_data(CACHE_KEY, a, True)
            return a

        return self.qbittorrent_cache.get_if_has_data(CACHE_KEY)


    def get_client_id(self, include_prefix:bool = True):

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

        client_tag =  CD.get_guid()

        if not self.client_id:
            self.client_id = client_tag

        logging.info(f"Client ID: {client_tag}")

        if not self.qbittorrent_initialized:
            return
        if CC.IS_PROFILE_MODE:
            self.qbittorrent.torrents_create_tags(['user_' + client_tag])


    def torrent_passes_filter(self, torrent_dict: dict):

        passes = True

        if CC.IS_PROFILE_MODE:

            tags = torrent_dict.get('tags', None)

            if tags:

                tags = set(tags.split(", "))

                if self.get_client_id() not in tags:
                    passes = False

            else:
                passes = False

        return passes
