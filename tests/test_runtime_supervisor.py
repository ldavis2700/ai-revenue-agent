import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import runtime_supervisor


class SupervisorTests(unittest.TestCase):
    def test_real_child_exit_terminates_sibling_and_requests_restart(self):
        children=[]
        def spawn(*args,**kwargs):
            child=subprocess.Popen(*args,**kwargs)
            children.append(child)
            return child
        result=runtime_supervisor.supervise([
            [sys.executable,'-c','import time; time.sleep(.1)'],
            [sys.executable,'-c','import time; time.sleep(60)']],popen=spawn)
        self.assertEqual(result,1)
        self.assertTrue(all(p.poll() is not None for p in children))

    def test_owner_stop_shuts_children_down_cleanly(self):
        stop=threading.Event()
        timer=threading.Timer(.1,stop.set)
        timer.start()
        try:
            self.assertEqual(runtime_supervisor.supervise(
                [[sys.executable,'-c','import time; time.sleep(60)']],stop),0)
        finally:timer.cancel()

    def test_spawn_failure_cleans_up_existing_child(self):
        children=[]
        def spawn(*args,**kwargs):
            if children:raise OSError('spawn failed')
            p=subprocess.Popen(*args,**kwargs);children.append(p);return p
        with self.assertRaises(OSError):
            runtime_supervisor.supervise([[sys.executable,'-c','import time; time.sleep(60)'],['missing']],popen=spawn)
        self.assertIsNotNone(children[0].poll())


if __name__=='__main__':unittest.main()
