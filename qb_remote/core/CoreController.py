import sys, os
import traceback
import time
import threading
import collections
import random
from typing import Callable
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

        self.torrent_files_cache = Cache.Expiring_Data_Cache(
            "torrent_files_cache", CC.TORRENT_CACHE_TIME_SECONDS
        )
        self.torrent_metadata_cache = Cache.Data_Cache("torrent_files_cache")
        self.file_priority_transaction_cache = Cache.Data_Cache("torrent_files_cache")
        self.syncronized_torrent_metadata_cache = Cache.Data_Cache(
            "syncronized_torrent_files_cache"
        )

        self._caches["torrent_files_cache"] = self.torrent_files_cache
        self._caches["torrent_metadata_cache"] = self.torrent_metadata_cache
        self._caches["file_priority_transaction_cache"] = self.file_priority_transaction_cache
        self._caches["syncronized_torrent_metadata_cache"] = self.syncronized_torrent_metadata_cache

        self._fast_job_scheduler = None
        self._slow_job_scheduler = None

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

    def shutdown_model(self):
        if self._fast_job_scheduler is not None:
            self._fast_job_scheduler.shutdown()

            self._fast_job_scheduler = None

        if self._slow_job_scheduler is not None:
            self._slow_job_scheduler.shutdown()

            self._slow_job_scheduler = None

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

    def boot_everything_base(self):
        # try:

        #     self.CheckAlreadyRunning()

        # except NyanExceptions.Shutdown_Exception:

        #     logging.warning("Already running this controller instance!")
        #     return

        try:
            self.init_model()

            self.init_view()

            self._is_booted = True

        except CE.Shutdown_Exception as e:
            logging.error(e)

        except Exception as e:
            trace = traceback.format_exc()

            logging.error(trace)

    def exit_everything_base(self):
        try:
            CG.started_shutdown = True

            self.shutdown_view()

            self.shutdown_model()

        except CE.Shutdown_Exception:
            pass

        except Exception as e:
            logging.error(traceback.format_exc())

        finally:
            self._program_is_shut_down = True

    ### Torrent Stuff

    def sync_metadata(self):
        cache = self.get_cache("syncronized_torrent_metadata_cache")

        with cache.get_lock():
            synced_meta: SyncMainDataDictionary = cache.get_if_has_data_unsafe(
                "syncronized_metadata"
            )

            if not synced_meta:
                synced_meta = CG.client_instance.sync_maindata()

                cache.add_data_unsafe("syncronized_metadata", synced_meta, True)

            else:
                updated_metadata = CG.client_instance.sync_maindata(rid=synced_meta.rid)

                CD.update_dictionary_no_key_remove(synced_meta, updated_metadata)

    def get_torrents(self, skip_cache=False, **kwargs):
        """
        Gets all torrent files, either from a cache or fresh,

        Cache expires ever 120 seconds
        """

        if not skip_cache and not kwargs:
            data = self.torrent_files_cache.get_if_has_non_expired_data("torrent_list")

            if data:
                logging.debug("Cache hit for 'torrent_list'")
                return data
            else:
                logging.debug("Cache miss for 'torrent_list'")

            data = CG.client_instance.torrents_info(**kwargs)

            self.torrent_files_cache.add_data("torrent_list", data, True)

            return data

        logging.debug(
            f"Custom call to torrent_info, skipping cache. kwargs = {kwargs}, skip_cache = {skip_cache}"
        )

        return CG.client_instance.torrents_info(**kwargs)

    def update_torrents_file_priority_transactional(
        self, torret_hash: str, file_id: int, priority: int
    ):
        """
        Updates the torrents files priority after 2 seconds,

        All function calls for the given torrent in that time will be added to the transaction,

        After the 2 seconds all the files will be updated to reflect the final state of the transaction
        """

        if not self.file_priority_transaction_cache.has_data(torret_hash):
            self.file_priority_transaction_cache.add_data(
                torret_hash, {"file_ids": [file_id], "priority": priority}, True
            )

            def callback(torrent_hash):
                c = self.get_cache("file_priority_transaction_cache")

                data = c.get_if_has_data(torrent_hash, True)

                logging.info(f"Updating torrent priority for {torrent_hash}")

                CG.client_instance.torrents_file_priority(
                    torrent_hash, data["file_ids"], data["priority"]
                )

            self.call_later(2, callback, torret_hash)

        else:
            self.file_priority_transaction_cache.get_data(torret_hash)["file_ids"].append(file_id)
