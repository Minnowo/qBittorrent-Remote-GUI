import threading
import subprocess
import time
import queue
import traceback
import os
import random
import bisect
from typing import Callable, TYPE_CHECKING

from . import CoreData as CD
from . import CoreExceptions as CE
from . import CoreGlobals as CG
from . import CoreLogging as logging

if TYPE_CHECKING:
    from . import CoreController as Controller


NEXT_THREAD_CLEAROUT: int = 0

THREADS_TO_THREAD_INFO: dict[threading.Thread, dict] = {}

THREAD_INFO_LOCK: threading.Lock = threading.Lock()


def die_if_thread_is_shutting_down():
    if is_thread_shutting_down():
        raise CE.Shutdown_Exception("Thread is shutting down!")


def clear_out_dead_threads():
    with THREAD_INFO_LOCK:
        for thread in list(THREADS_TO_THREAD_INFO.keys()):
            if not thread.is_alive():
                del THREADS_TO_THREAD_INFO[thread]


def get_thread_info(thread: threading.Thread = None):
    global NEXT_THREAD_CLEAROUT

    if CD.time_has_passed(NEXT_THREAD_CLEAROUT):
        clear_out_dead_threads()

        NEXT_THREAD_CLEAROUT = CD.time_now() + 600

    if thread is None:
        thread = threading.current_thread()

    with THREAD_INFO_LOCK:
        if thread not in THREADS_TO_THREAD_INFO:
            THREADS_TO_THREAD_INFO[thread] = {"shutting_down": False}

        return THREADS_TO_THREAD_INFO[thread]


def is_thread_shutting_down():
    if isinstance(threading.current_thread(), Daemon):

        if CG.started_shutdown:

            return True

    thread_info = get_thread_info()

    return thread_info["shutting_down"]


def shutdown_thread(thread: threading.Thread):
    thread_info = get_thread_info(thread)

    thread_info["shutting_down"] = True


class Job_Scheduler(threading.Thread):
    def __init__(self, controller):
        threading.Thread.__init__(self, name="Job Scheduler")

        self._controller = controller

        self._waiting: list[Schedulable_Job] = []

        self._waiting_lock = threading.Lock()

        self._new_job_arrived = threading.Event()

        self._current_job: Schedulable_Job = None

        self._cancel_filter_needed = threading.Event()
        self._sort_needed = threading.Event()

    def _filter_cancelled(self):
        with self._waiting_lock:
            self._waiting = [job for job in self._waiting if not job.is_cancelled()]

    def _get_loop_wait_time(self):
        with self._waiting_lock:
            if len(self._waiting) == 0:
                return 0.2

            next_job = self._waiting[0]

        time_delta_until_due = next_job.get_time_delta_until_due()

        return min(1.0, time_delta_until_due)

    def _no_work_to_start(self):
        with self._waiting_lock:
            if len(self._waiting) == 0:
                return True

            next_job = self._waiting[0]

        if next_job.is_due():
            return False

        else:
            return True

    def _sort_waiting(self):
        # sort the waiting jobs in ascending order of expected work time

        with self._waiting_lock:  # this uses __lt__ to sort
            self._waiting.sort()

    def _start_work(self):
        jobs_started = 0

        while True:
            with self._waiting_lock:
                if len(self._waiting) == 0:
                    break

                if jobs_started >= 10:  # try to avoid spikes
                    break

                next_job = self._waiting[0]

                if not next_job.is_due():
                    # front is not due, so nor is the rest of the list
                    break

                next_job = self._waiting.pop(0)

            if next_job.is_cancelled():
                continue

            if next_job.slot_ok():
                # important this happens outside of the waiting lock lmao!
                next_job.start_work()

                jobs_started += 1

            else:
                # delay is automatically set by SlotOK

                with self._waiting_lock:
                    bisect.insort(self._waiting, next_job)

    def add_job(self, job):
        with self._waiting_lock:
            bisect.insort(self._waiting, job)

        self._new_job_arrived.set()

    def clear_out_dead(self):
        with self._waiting_lock:
            self._waiting = [job for job in self._waiting if not job.is_dead()]

    def get_name(self):
        return "Job Scheduler"

    def get_current_job_summary(self):
        with self._waiting_lock:
            return CD.to_human_int(len(self._waiting)) + " jobs"

    def get_jobs(self):
        with self._waiting_lock:
            return list(self._waiting)

    def get_pretty_job_summary(self):
        with self._waiting_lock:
            num_jobs = len(self._waiting)

            job_lines = [repr(job) for job in self._waiting]

            lines = [CD.to_human_int(num_jobs) + " jobs:"] + job_lines

            text = os.linesep.join(lines)

            return text

    def job_cancelled(self):
        self._cancel_filter_needed.set()

    def shutdown(self):
        shutdown_thread(self)

        self._new_job_arrived.set()

    def work_times_have_changed(self):
        self._sort_needed.set()

    def run(self):
        while True:
            try:
                while self._no_work_to_start():
                    if is_thread_shutting_down():
                        return

                    if self._cancel_filter_needed.is_set():
                        self._filter_cancelled()

                        self._cancel_filter_needed.clear()

                    if self._sort_needed.is_set():
                        self._sort_waiting()

                        self._sort_needed.clear()

                        continue  # if some work is now due, let's do it!

                    wait_time = self._get_loop_wait_time()

                    self._new_job_arrived.wait(wait_time)

                    self._new_job_arrived.clear()

                self._start_work()

            except CE.Shutdown_Exception:
                return

            except Exception as e:
                logging.error(traceback.format_exc())

            time.sleep(0.00001)


class Schedulable_Job(object):
    PRETTY_CLASS_NAME = "job base"

    def __init__(
        self,
        controller: "Controller.ClientController",
        scheduler: Job_Scheduler,
        initial_delay_seconds: float,
        work_callable: CD.Call,
    ):
        self._controller = controller
        self._scheduler = scheduler
        self._work_callable = work_callable

        self._should_delay_on_wakeup = False

        self._next_work_time = CD.time_now_float() + initial_delay_seconds

        self._thread_slot_type = None

        self._work_lock = threading.Lock()

        self._currently_working = threading.Event()
        self._is_cancelled = threading.Event()

        self._thread = None

    def __lt__(self, other: "Schedulable_Job"):  # for the scheduler to do bisect.insort noice
        return self._next_work_time < other._next_work_time

    def __repr__(self):
        return "{}: {} {}".format(
            self.PRETTY_CLASS_NAME, self.get_pretty_job(), self.get_due_string()
        )

    def _boot_worker(self):

        self._controller.call_to_thread(self.work)

    def cancel(self):
        self._is_cancelled.set()

        self._scheduler.job_cancelled()

    def is_currently_working(self):
        return self._currently_working.is_set()

    def get_due_string(self):
        due_delta = self._next_work_time - CD.time_now_float()

        due_string = CD.time_delta_to_pretty_time_delta(due_delta)

        if due_delta < 0:
            due_string = "was due {} ago".format(due_string)

        else:
            due_string = "due in {}".format(due_string)

        return due_string

    def get_next_work_time(self):
        return self._next_work_time

    def get_pretty_job(self):
        return repr(self._work_callable)

    def get_time_delta_until_due(self):
        return CD.time_delta_until_time_float(self._next_work_time)

    def is_cancelled(self):
        return self._is_cancelled.is_set()

    def is_dead(self):
        return False

    def is_due(self):
        return CD.time_has_passed_float(self._next_work_time)

    def pub_sub_wake(self, *args, **kwargs):
        self.wake()

    def set_thread_slot_type(self, thread_type):
        self._thread_slot_type = thread_type

    def should_delay_on_wakeup(self, value):
        self._should_delay_on_wakeup = value

    def slot_ok(self):
        if self._thread_slot_type is not None:
            if self._controller.can_acquire_thread_slot(self._thread_slot_type):
                return True

            else:
                self._next_work_time = CD.time_now_float() + 10 + random.random()

                return False

        return True

    def start_work(self):
        if self._is_cancelled.is_set():
            return

        self._currently_working.set()

        self._boot_worker()

    def wake(self, next_work_time=None):
        if next_work_time is None:
            next_work_time = CD.time_now_float()

        self._next_work_time = next_work_time

        self._scheduler.work_times_have_changed()

    def work(self):
        try:
            if self._should_delay_on_wakeup:
                while self._controller.just_woke_from_sleep():
                    if is_thread_shutting_down():
                        return

                    time.sleep(1)

            with self._work_lock:
                self._work_callable()

        finally:
            if self._thread_slot_type is not None:
                self._controller.release_thread_slot(self._thread_slot_type)

            self._currently_working.clear()


class Single_Job(Schedulable_Job):
    PRETTY_CLASS_NAME = "single job"

    def __init__(
        self,
        controller: "Controller.ClientController",
        scheduler: Job_Scheduler,
        initial_delay_seconds: float,
        work_callable: CD.Call,
    ):
        Schedulable_Job.__init__(self, controller, scheduler, initial_delay_seconds, work_callable)

        self._work_complete = threading.Event()

    def is_work_complete(self):
        return self._work_complete.is_set()

    def work(self):
        Schedulable_Job.work(self)

        self._work_complete.set()


class Repeating_Job(Schedulable_Job):
    PRETTY_CLASS_NAME = "repeating job"

    def __init__(
        self,
        controller: "Controller.ClientController",
        scheduler: Job_Scheduler,
        initial_delay: float,
        period: float,
        work_callable: CD.Call,
    ):
        Schedulable_Job.__init__(self, controller, scheduler, initial_delay, work_callable)

        self._period = period

        self._stop_repeating = threading.Event()

    def cancel(self):
        Schedulable_Job.cancel(self)

        self._stop_repeating.set()

    def delay(self, delay):
        self._next_work_time = CD.time_now_float() + delay

        self._scheduler.work_times_have_changed()

    def is_repeating_work_finished(self):
        return self._stop_repeating.is_set()

    def start_work(self):
        if self._stop_repeating.is_set():
            return

        Schedulable_Job.start_work(self)

    def work(self):
        Schedulable_Job.work(self)

        if not self._stop_repeating.is_set():
            self._next_work_time = CD.time_now_float() + self._period

            self._scheduler.add_job(self)












class Daemon(threading.Thread):
    def __init__(self, controller:"Controller.ClientController", name: str):

        threading.Thread.__init__(self, name=name)

        self._controller = controller
        self._name = name

        self._event = threading.Event()

    def _do_pre_call(self):

        if CG.daemon_report_mode:

            logging.info(self._name + " doing a job.")

    def get_current_job_summary(self):

        return "unknown job"

    def get_name(self):

        return self._name

    def shutdown(self):

        shutdown_thread(self)

        self.wake()

    def wake(self):

        self._event.set()



class Thread_Call_To_Thread(Daemon):
    """
    A Daemon Worker thread.

    This thread must be started manually.

    This thread waits until a given callback is recieved before performing any jobs.
    """

    def __init__(self, controller: "Controller.ClientController", name: str):

        Daemon.__init__(self, controller, name)

        self._callable = None

        self._queue: queue.Queue[tuple[Callable]] = queue.Queue()
        
        # start off true so new threads aren't used twice by two quick successive calls
        self._currently_working = True  

    def is_currently_working(self):

        return self._currently_working

    def get_current_job_summary(self):

        return self._callable

    def put(self, callable: Callable, *args, **kwargs):

        self._currently_working = True

        self._queue.put((callable, args, kwargs))

        self._event.set()

    def run(self):

        try:

            while True:

                while self._queue.empty():

                    die_if_thread_is_shutting_down()

                    self._event.wait(10.0)

                    self._event.clear()

                die_if_thread_is_shutting_down()

                try:

                    try:

                        (callable, args, kwargs) = self._queue.get(1.0)

                    except queue.Empty:

                        # https://github.com/hydrusnetwork/hydrus/issues/750
                        # this shouldn't happen, but...
                        # even if we assume we'll never get this, we don't want to make a business of hanging forever on things

                        continue

                    self._do_pre_call()

                    self._callable = (callable, args, kwargs)

                    callable(*args, **kwargs)

                    self._callable = None

                    del callable

                except CE.Shutdown_Exception:

                    return

                except Exception as e:

                    logging.error(traceback.format_exc())

                finally:

                    self._currently_working = False

                time.sleep(0.00001)

        except CE.Shutdown_Exception:

            return
