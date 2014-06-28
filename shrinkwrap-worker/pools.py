from queue import Queue
import collections

if not hasattr(Queue, 'task_done'):
    from .QueueWrapper import Queue

from .workers import Worker
from .jobs import SimpleJob, SuicideJob


__all__ = ['ShrinkWrapWorker', 'default_worker_factory']


def default_worker_factory(job_queue):
    return Worker(job_queue)


class ShrinkWrapWorker(Queue):
    """
    ShrinkWrapWorker servers two functions: It is a Queue and a master of Worker
    threads. The Queue accepts Job objects and passes it on to Workers, who are
    initialized during the construction of the pool and by using grow().

    Jobs are inserted into the ShrinkWrapWorker with the `put` method.
    Hint: Have the Job append its result into a shared queue that the caller
    holds and then the caller reads an expected number of results from it.

    The shutdown() method must be explicitly called to terminate the Worker
    threads when the pool is no longer needed.

    Construction parameters:

    size = 1
        Number of active worker threads the pool should contain.

    maxjobs = 0
        Maximum number of jobs to allow in the queue at a time. Will block on
        `put` if full.

    default_worker = default_worker_factory
        The default worker factory is called with one argument, which is the
        jobs Queue object that it will read from to acquire jobs. The factory
        will produce a Worker object which will be added to the pool.
    """

    def __init__(self, size=1, maxjobs=0, worker_factory=default_worker_factory):
        if not isinstance(worker_factory, collections.Callable):
            raise TypeError("worker_factory must be callable")

        self.worker_factory = worker_factory  # Used to build new workers
        self._size = 0  # Number of active workers we have

        # Initialize the Queue
        Queue.__init__(self, maxjobs)  # The queue contains job that are read by workers
        self._jobs = self  # Pointer to the queue, for backwards compatibility with version 0.9.1 and earlier

        # Hire some workers!
        for i in range(size):
            self.grow()

    def grow(self):
        "Add another worker to the pool."
        t = self.worker_factory(self)
        t.start()
        self._size += 1

    def shrink(self):
        "Get rid of one worker from the pool. Raises IndexError if empty."
        if self._size <= 0:
            raise IndexError("pool is already empty")
        self._size -= 1
        self.put(SuicideJob())

    def shutdown(self):
        "Retire the workers."
        for i in range(self.size()):
            self.put(SuicideJob())

    def size(self):
        "Approximate number of active workers (could be more if a shrinking is in progress)."
        return self._size

    def map(self, fn, *seq):
        "Perform a map operation distributed among the workers. Will block until done."
        results = Queue()
        args = list(zip(*seq))
        for seq in args:
            j = SimpleJob(results, fn, seq)
            self.put(j)

        # Aggregate results
        r = []
        for i in range(len(args)):
            r.append(results.get())

        return r

    def join(self):
        self.join()
