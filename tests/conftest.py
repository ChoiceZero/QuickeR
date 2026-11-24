"""Runs the real QuickeR app (src/main.py) in-process against a fake Flet client.

`main(page)` builds the whole UI on a real `ft.Page` owned by a real Flet
`Session`. The only stand-in is the connection: instead of a Flutter client
it records the messages the session sends. Tests act like the client would:
they patch control properties and dispatch events through the session, so
every handler runs through Flet's normal event pipeline.
"""
import asyncio
import dataclasses
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import msgpack
import pytest

# The app creates its data folders at import time. Point them at a throwaway
# folder (honoured on Linux) so importing it never touches the real library.
os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="quicker-tests-")

import flet as ft  # noqa: E402
from flet.controls.base_control import BaseControl  # noqa: E402
from flet.controls.context import _context_page, context  # noqa: E402
from flet.messaging.connection import Connection  # noqa: E402
from flet.messaging.protocol import (  # noqa: E402
    ClientAction,
    ClientMessage,
    RegisterClientResponseBody,
    configure_encode_object_for_msgpack,
)
from flet.messaging.session import Session  # noqa: E402
from flet.pubsub.pubsub_hub import PubSubHub  # noqa: E402

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))

# main.py ends with `ft.run(main)`; stop it from opening a window on import.
_real_run = ft.run
ft.run = lambda *args, **kwargs: None
try:
    import main as app  # noqa: E402
finally:
    ft.run = _real_run


class RecordingConnection(Connection):
    """A Flet connection with no client behind it: it keeps what is sent.

    Messages are still encoded exactly as the socket server encodes them,
    because encoding is where Flet snapshots the control tree for the next
    diff. Skipping it would leave later updates unsent and unmounted."""

    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.executor = ThreadPoolExecutor()
        self.pubsubhub = PubSubHub(loop=loop, executor=self.executor)
        self.messages = []

    def send_message(self, message):
        msgpack.packb(
            [message.action, message.body],
            default=configure_encode_object_for_msgpack(BaseControl),
        )
        self.messages.append(message)

    def dispose(self):
        self.executor.shutdown(wait=False)


def walk(control):
    """Yields `control` and every control below it."""
    seen = set()
    stack = [control]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        yield node
        for field in dataclasses.fields(node):
            if field.name.startswith("_") or field.name == "parent":
                continue
            value = getattr(node, field.name, None)
            items = value if isinstance(value, list) else [value]
            stack.extend(item for item in items if isinstance(item, BaseControl))


class AppDriver:
    """Drives a running app the way the Flutter client would."""

    def __init__(self, session, conn, errors):
        self.session = session
        self.conn = conn
        self.errors = errors

    @property
    def page(self):
        return self.session.page

    def roots(self):
        page = self.page
        yield page
        yield from page.overlay
        yield from page._dialogs.controls

    def find_all(self, predicate):
        found = []
        for root in self.roots():
            found.extend(c for c in walk(root) if predicate(c))
        return found

    def find(self, predicate):
        found = self.find_all(predicate)
        assert found, "no control matched"
        return found[0]

    def text_of(self, control):
        """All text shown inside a control, joined by spaces."""
        return " ".join(
            str(c.value) for c in walk(control) if isinstance(c, ft.Text) and c.value
        )

    async def event(self, control, name, data=None):
        await self.session.dispatch_event(control._i, name, data)
        await self.settle()

    async def click(self, control):
        await self.event(control, "click")

    async def type_text(self, field, text):
        # The client first syncs the new value, then fires on_change.
        self.session.apply_patch(field._i, {"value": text})
        await self.event(field, "change", text)

    async def settle(self, seconds=0.3):
        """Lets debounced previews and background tasks finish."""
        await asyncio.sleep(seconds)
        self.assert_no_errors()

    def assert_no_errors(self):
        crashes = [
            m.body.message
            for m in self.conn.messages
            if m.action == ClientAction.SESSION_CRASHED
        ]
        assert not crashes, "app reported an error:\n" + "\n".join(crashes)
        assert not self.errors, "background task failed:\n" + "\n".join(self.errors)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """An empty QuickeR data folder with the first-run tutorial already done."""
    qr_dir = tmp_path / "qr_codes"
    pinned_dir = tmp_path / "pinned_qr_codes"
    qr_dir.mkdir()
    pinned_dir.mkdir()
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "Theme_color": "#ff1e88e5",
        "Appearance": "System",
        "First_run": False,
        "GridMode": "True",
        "Check_updates": False,
        "Language": "en",
    }))
    monkeypatch.setattr(app, "QR_DIR", str(qr_dir))
    monkeypatch.setattr(app, "PINNED_DIR", str(pinned_dir))
    monkeypatch.setattr(app, "SETTINGS_PATH", str(settings))
    # No network in tests: skip the GitHub release check.
    monkeypatch.setitem(app.STARTUP, "update_checked", True)
    monkeypatch.setitem(app.SORT_STATE, "newest_first", True)
    monkeypatch.setitem(app.DETAILS_RESIZE_HOOK, "fn", None)
    return tmp_path


@pytest.fixture
async def start_app(data_dir):
    """Returns a coroutine that starts the app and gives back an AppDriver."""
    drivers = []

    async def start(width=1280, height=800, platform="linux"):
        loop = asyncio.get_running_loop()
        errors = []

        def on_task_error(loop, ctx):
            exc = ctx.get("exception")
            errors.append(f"{ctx.get('message')}: {exc!r}")

        loop.set_exception_handler(on_task_error)
        conn = RecordingConnection(loop)
        # Same steps as Flet's socket server when a desktop client registers.
        session = Session(conn)
        session.apply_page_patch({"width": width, "height": height, "platform": platform})
        conn.send_message(ClientMessage(
            ClientAction.REGISTER_CLIENT,
            RegisterClientResponseBody(
                session_id=session.id, page_patch=session.get_page_patch(), error=""
            ),
        ))
        session.attach_connection(conn)
        # What flet.app does once the session exists: run main, then flush.
        _context_page.set(session.page)
        context.reset_auto_update()
        app.main(session.page)
        await session.after_event(session.page)
        driver = AppDriver(session, conn, errors)
        drivers.append(driver)
        await driver.settle()
        return driver

    yield start

    for driver in drivers:
        driver.session.close()
        await asyncio.sleep(0)
        driver.conn.dispose()
    app.set_language(app.DEFAULT_LANGUAGE)
