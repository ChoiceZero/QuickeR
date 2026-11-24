"""Writes crash logs to files that the user can view, copy or share from settings.

Only the standard library is used. Each app session that hits an unhandled
error gets one file, crash-<timestamp>.log, in the logs folder. These sources
are captured:

- Errors that Flet catches in event handlers and in main() (the "flet" logger).
- Exceptions in background tasks (the "asyncio" logger).
- Uncaught exceptions in the main thread and in other threads.
- Native crashes such as segfaults (faulthandler). These are written to a
  scratch file and turned into a crash log on the next start.
"""
import datetime
import faulthandler
import logging
import os
import platform
import sys
import threading

MAX_LOGS = 10
MAX_LOG_BYTES = 1_000_000  # An error that repeats (say, on every resize) must not fill the disk.
_PREFIX = "crash-"
_SUFFIX = ".log"
_NATIVE_PREFIX = ".native-"


class CrashLog:
    def __init__(self, log_dir, app_version):
        self.log_dir = log_dir
        self.app_version = app_version
        self._path = None
        self._lock = threading.Lock()
        self._native_file = None
        self._full = False

    def _header(self, title, when=None):
        when = when or datetime.datetime.now()
        return (
            f"QuickeR {self.app_version} - {title}\n"
            f"Time: {when.isoformat(timespec='seconds')}\n"
            f"OS: {platform.platform()}\n"
            f"Python: {sys.version.split()[0]}\n"
            + "-" * 60 + "\n"
        )

    def _new_path(self):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        return os.path.join(self.log_dir, f"{_PREFIX}{stamp}{_SUFFIX}")

    def _prune(self):
        for old in list_logs(self.log_dir)[MAX_LOGS:]:
            try:
                os.remove(old)
            except OSError:
                pass

    def write(self, text):
        """Appends text to this session's crash log, creating it on first use."""
        with self._lock:
            try:
                os.makedirs(self.log_dir, exist_ok=True)
                if self._path is None:
                    self._path = self._new_path()
                    with open(self._path, "w", encoding="utf-8") as f:
                        f.write(self._header("crash log"))
                    self._prune()
                if self._full:
                    return
                with open(self._path, "a", encoding="utf-8") as f:
                    if os.path.getsize(self._path) + len(text) >= MAX_LOG_BYTES:
                        self._full = True
                        f.write("[Log size limit reached; later errors are not recorded.]\n")
                    else:
                        f.write(text.rstrip("\n") + "\n\n")
            except OSError:
                pass  # Never let logging itself take the app down.

    def _collect_native_crashes(self):
        """Turns faulthandler output left by a previous session into a crash log."""
        try:
            names = os.listdir(self.log_dir)
        except OSError:
            return
        for name in names:
            if not name.startswith(_NATIVE_PREFIX):
                continue
            path = os.path.join(self.log_dir, name)
            try:
                crashed_at = datetime.datetime.fromtimestamp(os.path.getmtime(path))
                with open(path, encoding="utf-8", errors="replace") as f:
                    dump = f.read()
                os.remove(path)  # Fails on Windows if another instance still has it open.
            except OSError:
                continue
            if dump.strip():
                target = self._new_path()
                with open(target, "w", encoding="utf-8") as f:
                    f.write(self._header("native crash (previous session)", crashed_at) + dump)
                self._prune()

    def install(self):
        os.makedirs(self.log_dir, exist_ok=True)
        self._collect_native_crashes()

        handler = _Handler(self)
        handler.setLevel(logging.ERROR)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        logging.getLogger().addHandler(handler)

        previous_hook = sys.excepthook

        def excepthook(exc_type, exc, tb):
            if not issubclass(exc_type, KeyboardInterrupt):
                logging.getLogger("quicker").critical("Uncaught exception", exc_info=(exc_type, exc, tb))
            previous_hook(exc_type, exc, tb)

        sys.excepthook = excepthook

        previous_thread_hook = threading.excepthook

        def thread_excepthook(args):
            if not issubclass(args.exc_type, SystemExit):
                name = args.thread.name if args.thread else "unknown"
                logging.getLogger("quicker").critical(
                    "Uncaught exception in thread %s", name,
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                )
            previous_thread_hook(args)

        threading.excepthook = thread_excepthook

        try:
            native_path = os.path.join(self.log_dir, f"{_NATIVE_PREFIX}{os.getpid()}.txt")
            self._native_file = open(native_path, "w", encoding="utf-8")
            faulthandler.enable(file=self._native_file, all_threads=True)
        except (OSError, RuntimeError, ValueError):
            pass


class _Handler(logging.Handler):
    def __init__(self, crash_log):
        super().__init__()
        self.crash_log = crash_log

    def emit(self, record):
        try:
            self.crash_log.write(self.format(record))
        except Exception:
            self.handleError(record)


def list_logs(log_dir):
    """Returns the crash log paths, newest first."""
    try:
        names = [n for n in os.listdir(log_dir) if n.startswith(_PREFIX) and n.endswith(_SUFFIX)]
    except OSError:
        return []
    return [os.path.join(log_dir, n) for n in sorted(names, reverse=True)]


def latest_log(log_dir):
    """Returns the newest crash log path, or None."""
    logs = list_logs(log_dir)
    return logs[0] if logs else None


def install(log_dir, app_version):
    crash_log = CrashLog(log_dir, app_version)
    crash_log.install()
    return crash_log
