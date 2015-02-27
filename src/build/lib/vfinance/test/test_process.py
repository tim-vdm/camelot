"""
Test the multiprocessing building blocks
"""

import unittest

from vfinance.process import WorkerProcess, WorkerPool

class ProcessCase(unittest.TestCase):

    def test_worker_process(self):
        worker = WorkerProcess()
        with self.assertRaises(Exception):
            for step in worker.send_work(1):
                pass
        worker.start()
        with self.assertRaises(Exception):
            worker._receive_work()
        for step in worker.send_work(3.14):
            result = step
        self.assertEqual(result, 3.14)
        worker.stop()
        worker.join(5)
        self.assertEqual(worker.exitcode, 0)

    def test_worker_pool(self):
        result = []
        with WorkerPool(WorkerProcess) as pool:
            result = list(pool.submit(xrange(1000)))
        self.assertEqual(result, list(xrange(1000)))
        for worker in pool.workers:
            self.assertFalse(worker.is_alive())
