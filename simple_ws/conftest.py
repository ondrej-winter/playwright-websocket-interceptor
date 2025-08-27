# conftest.py
# Playwright (Python, sync) — dynamic per‑test WebSocket mutation
# Requires Playwright >= 1.48 (route_web_socket / WebSocketRoute)
# Docs:
# - WebSocketRoute API: https://playwright.dev/python/docs/api/class-websocketroute
# - Release notes (WS routing): https://playwright.dev/docs/release-notes

from __future__ import annotations
import json
import pytest
from dataclasses import dataclass
from typing import Callable, Literal, Union

Msg = Union[str, bytes]
Mode = Literal["untouched", "constant", "increasing", "decreasing"]


@dataclass
class WSBehavior:
    """Mutable controls for a single test.

    Tests can call ws_behavior.set_mode(...) at any time to switch behavior.
    By default, traffic is proxied untouched.
    """

    url_pattern: str = "**/ws"           # which WS URLs to intercept
    mode: Mode = "untouched"             # current mode
    value_key: str = "value"             # JSON field to patch
    const_value: float = 0.0              # for constant mode
    _incr: float = 0.0                    # current value for increasing
    _decr: float = 100.0                  # current value for decreasing
    _step: float = 1.0                    # step for inc/dec

    # Optional custom hooks; if set, they run after mode logic
    inbound_hook: Callable[[Msg], Msg] | None = None   # server -> page
    outbound_hook: Callable[[Msg], Msg] | None = None  # page -> server

    def set_mode(
        self,
        mode: Mode,
        *,
        start: float | None = None,
        step: float | None = None,
        const: float | None = None,
        value_key: str | None = None,
    ) -> None:
        """Switch behavior live during a test.

        Args:
            mode: one of "untouched", "constant", "increasing", "decreasing".
            start: starting value for increasing/decreasing.
            step: increment/decrement per frame.
            const: constant value for constant mode.
            value_key: override which JSON field to patch.
        """
        self.mode = mode
        if const is not None:
            self.const_value = const
        if start is not None:
            self._incr = start
            self._decr = start
        if step is not None:
            self._step = step
        if value_key is not None:
            self.value_key = value_key


@pytest.fixture
def ws_behavior() -> WSBehavior:
    """Per-test behavior object. Modify it inside tests as needed."""
    return WSBehavior()


@pytest.fixture(autouse=True)
def install_ws_router(page, ws_behavior: WSBehavior):
    """Auto-install a WS proxy for each test.

    Default: passthrough. Tests can call ws_behavior.set_mode(...) to switch to
    constant/increasing/decreasing mid-test. The route is attached to THIS page
    only, so parallel tests stay isolated.
    """

    def handler(ws_route):
        # Connect to the real backend; we are in proxy mode now.
        server = ws_route.connect_to_server()

        # Per-connection counters (do not bleed across sockets)
        state = {"incr": ws_behavior._incr, "decr": ws_behavior._decr}

        def patch_inbound(msg: Msg) -> Msg:
            """server -> page mutation according to current mode."""
            if isinstance(msg, (bytes, bytearray)):
                return ws_behavior.inbound_hook(msg) if ws_behavior.inbound_hook else msg
            try:
                obj = json.loads(msg)
            except Exception:
                return ws_behavior.inbound_hook(msg) if ws_behavior.inbound_hook else msg

            m = ws_behavior.mode
            if m == "constant":
                obj[ws_behavior.value_key] = ws_behavior.const_value
            elif m == "increasing":
                obj[ws_behavior.value_key] = state["incr"]
                state["incr"] += ws_behavior._step
            elif m == "decreasing":
                obj[ws_behavior.value_key] = state["decr"]
                state["decr"] -= ws_behavior._step
            # "untouched" -> no change

            out = json.dumps(obj)
            return ws_behavior.inbound_hook(out) if ws_behavior.inbound_hook else out

        def patch_outbound(msg: Msg) -> Msg:
            """page -> server (left unchanged unless a hook is set)."""
            if ws_behavior.outbound_hook:
                return ws_behavior.outbound_hook(msg)
            return msg

        # Once handlers are attached, you MUST forward messages manually.
        ws_route.on_message(lambda m: server.send(patch_outbound(m)))   # page -> server
        server.on_message(lambda m: ws_route.send(patch_inbound(m)))    # server -> page

    # Register before navigation so sockets are routed.
    page.route_web_socket(ws_behavior.url_pattern, handler)
    yield
    # Teardown handled automatically when page/context closes.
