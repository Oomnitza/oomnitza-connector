# -*- coding: utf-8 -*-
"""http://code.activestate.com/recipes/578453-python-single-instance-cross-platform/.

This guy is used to keep an app to a single instance.

Example
-------
    This is setup to be used with the `with` statement, as so::

        with SingleInstance("This app is already running!"):
            for i in range(20, 0, -1):
                print i
                time.sleep(1)

"""

import sys
import os
import logging
import tempfile

LOGGER = logging.getLogger(__name__)

OS_WIN = False
if 'win32' in sys.platform.lower():
    OS_WIN = True
else:
    import fcntl


class SingleInstance:

    enabled = True

    def __init__(self, enabled=True, exit_msg=None, lock_path=None, lock_file=None):
        """Use me to keep this app to a single instance.

        Parameters
        ----------
            exit_msg : basestring
                Defaults to None. If provided, this message will be used to exist the app if another instance is already running.
            lock_path : basestring
                Defaults to None. The full path to the lock file.
            lock_file :basestring
                Defaults to None. The filename to use when generating the lock_path.

        """
        self.enabled = enabled

        if self.enabled:
            self._exit_msg = exit_msg or "This app is already running!"
            if lock_path:
                self._lock_path = lock_path
            else:
                if not lock_file:
                    lock_file = os.path.split(sys.argv[0]+'.lock')[-1]
                tmp_dir = tempfile.gettempdir()
                self._lock_path = os.path.join(tmp_dir, lock_file)

            self._fh = None
            self._is_already_running = False
            self._do_magic()
            if exit_msg and self._is_already_running:
                LOGGER.exception("{}.\n  File '{}' exists and is locked.".format(exit_msg, self._lock_path))
                sys.exit()

    @property
    def is_already_running(self):
        return self._is_already_running

    def __enter__(self):
        if self.enabled:
            LOGGER.debug("SingleInstance.__enter__() has been entered.")

    def __exit__(self, type, value, traceback):
        if self.enabled:
            LOGGER.debug("SingleInstance.__exit__() has been entered.")
            self._clean_up()

    def _do_magic(self):
        LOGGER.debug("Acquiring SingleInstance LOCK on %s.", self._lock_path)
        if OS_WIN:
            try:
                if os.path.exists(self._lock_path):
                    os.unlink(self._lock_path)
                self._fh = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except EnvironmentError as err:
                if err.errno == 13:
                    self._is_already_running = True
                else:
                    raise
        else:
            try:
                self._fh = open(self._lock_path, 'w')
                fcntl.lockf(self._fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fh.write("PID: {}\n".format(os.getpid()))
                self._fh.flush()
            except EnvironmentError as err:
                if self._fh is not None:
                    self._is_already_running = True
                else:
                    raise

    def _clean_up(self):
        LOGGER.debug("Cleaning up SingleInstance LOCK.")
        # this is not really needed
        try:
            if self._fh is not None:
                if OS_WIN:
                    os.close(self._fh)
                    os.unlink(self._lock_path)
                else:
                    fcntl.lockf(self._fh, fcntl.LOCK_UN)
                    self._fh.close()  # ???
                    os.unlink(self._lock_path)
        except OSError as exp:
            LOGGER.warning("OSError in SingleInstance.clean_up(): %s", str(exp))
        except Exception as exp:
            # raise # for debugging porpuses, do not raise it on production
            LOGGER.exception("Exception in SingleInstance.clean_up(): %s", str(exp))
