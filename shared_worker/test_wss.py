from playwright.sync_api import sync_playwright
import json

"""
Run: python shared_worker/test_wss.py

This script demonstrates JS-level interception using page.add_init_script for:
  • WebSocket (send/recv) created in the page context
  • SharedWorker <-> page MessagePort traffic (postMessage + onmessage)

Notes:
  - This logs to the page console; we bridge those logs to Python via page.on("console").
  - If the SharedWorker itself opens a WebSocket *inside the worker*, that WS is not visible
    to this JS patch (because add_init_script runs in the page, not in the worker).
    For low-level WS frames regardless of origin, prefer browser_context.route_web_socket(...)
    with Playwright ≥ 1.48. This file focuses on a reliable JS-only approach.
    Modes now supported: "untouched", "constant", "increasing" (start+step), "decreasing" (start+step)
"""

INIT_SCRIPT_TEMPLATE = r"""
(() => {
  try {
    // Global runtime config (controlled from tests via page.evaluate)
    // mode: "untouched" | "constant" | "increasing" | "decreasing"
    // constant: number used when mode === "constant"
    // start, step: used when mode is increasing/decreasing; `current` is advanced each message
    window.__ws_intercept__ = window.__ws_intercept__ || {
      mode: %(initial_mode)s,
      constant: %(constant_value)s,
      start: %(start_value)s,
      step: %(step_value)s,
      current: %(start_value)s
    };
    const cfg = window.__ws_intercept__;

    const nextValue = () => {
      switch (cfg.mode) {
        case 'untouched':
          return null; // do not mutate
        case 'constant':
          return Number(cfg.constant);
        case 'increasing': {
          const v = Number(cfg.current);
          cfg.current = v + Number(cfg.step);
          return v;
        }
        case 'decreasing': {
          const v = Number(cfg.current);
          cfg.current = v - Number(cfg.step);
          return v;
        }
        default:
          return null;
      }
    };

    const mutateValueField = (data) => {
      const target = nextValue();
      if (target === null) return data; // untouched

      // Case 1: structured object (e.g. {type, payload: {value}} or top-level {value})
      if (data && typeof data === 'object') {
        if (Object.prototype.hasOwnProperty.call(data, 'value')) {
          return { ...data, value: target };
        }
        if (data.payload && typeof data.payload === 'object' && Object.prototype.hasOwnProperty.call(data.payload, 'value')) {
          return { ...data, payload: { ...data.payload, value: target } };
        }
        return data;
      }

      // Case 2: JSON string
      if (typeof data === 'string' && data.includes('"value"')) {
        try {
          const obj = JSON.parse(data);
          if (obj && typeof obj === 'object') {
            if (Object.prototype.hasOwnProperty.call(obj, 'value')) {
              obj.value = target;
              return JSON.stringify(obj);
            }
            if (obj.payload && typeof obj.payload === 'object' && Object.prototype.hasOwnProperty.call(obj.payload, 'value')) {
              obj.payload.value = target;
              return JSON.stringify(obj);
            }
          }
        } catch (_) {}
      }
      return data;
    };

    // --- Intercept WebSocket in the PAGE context ---
    const OrigWS = window.WebSocket;
    if (OrigWS && !OrigWS.__patched_by_tests__) {
      const PatchedWS = function(url, protocols) {
        const ws = new OrigWS(url, protocols);
        const origSend = ws.send;
        ws.send = function(data) {
          try { console.log('[WS send]', data); } catch (_) {}
          return origSend.call(this, data);
        };
        const origAdd = ws.addEventListener.bind(ws);
        ws.addEventListener = function(type, listener, options) {
          if (type === 'message' && typeof listener === 'function') {
            const wrapped = function(ev) {
              const mutatedData = mutateValueField(ev && ev.data);
              try { console.log('[WS recv]', mutatedData); } catch (_) {}
              const newEv = new MessageEvent('message', { data: mutatedData });
              return listener.call(this, newEv);
            };
            return origAdd(type, wrapped, options);
          }
          return origAdd(type, listener, options);
        };
        Object.defineProperty(ws, 'onmessage', {
          configurable: true,
          enumerable: true,
          get() { return this.__onmessage_original || null; },
          set(fn) {
            this.__onmessage_original = fn;
            if (typeof fn === 'function') {
              const wrapped = (ev) => {
                const mutatedData = mutateValueField(ev && ev.data);
                try { console.log('[WS recv]', mutatedData); } catch (_) {}
                const newEv = new MessageEvent('message', { data: mutatedData });
                return fn.call(ws, newEv);
              };
              if (this.__onmessage_wrapped) {
                try { ws.removeEventListener('message', this.__onmessage_wrapped); } catch (_) {}
              }
              this.__onmessage_wrapped = wrapped;
              ws.addEventListener('message', wrapped);
            }
          },
        });
        return ws;
      };
      PatchedWS.prototype = OrigWS.prototype;
      PatchedWS.__patched_by_tests__ = true;
      Object.defineProperty(window, 'WebSocket', { value: PatchedWS });
    }

    // --- Intercept SharedWorker port messaging ---
    const OrigSW = window.SharedWorker;
    if (OrigSW && !OrigSW.__patched_by_tests__) {
      const PatchedSW = function(...args) {
        const worker = new OrigSW(...args);
        const port = worker.port;
        if (port) {
          const origPost = port.postMessage;
          port.postMessage = function(data, ...rest) {
            try { console.log('[SW post ->]', data); } catch (_) {}
            return origPost.call(this, data, ...rest);
          };
          const origAdd = port.addEventListener.bind(port);
          port.addEventListener = function(type, listener, options) {
            if (type === 'message' && typeof listener === 'function') {
              const wrapped = function(ev) {
                const mutatedData = mutateValueField(ev && ev.data);
                try { console.log('[SW <- recv]', mutatedData); } catch (_) {}
                const newEv = new MessageEvent('message', { data: mutatedData });
                return listener.call(this, newEv);
              };
              return origAdd(type, wrapped, options);
            }
            return origAdd(type, listener, options);
          };
          Object.defineProperty(port, 'onmessage', {
            configurable: true,
            enumerable: true,
            get() { return this.__onmessage_original || null; },
            set(fn) {
              this.__onmessage_original = fn;
              if (typeof fn === 'function') {
                const wrapped = (ev) => {
                  const mutatedData = mutateValueField(ev && ev.data);
                  try { console.log('[SW <- recv]', mutatedData); } catch (_) {}
                  const newEv = new MessageEvent('message', { data: mutatedData });
                  return fn.call(port, newEv);
                };
                if (this.__onmessage_wrapped) {
                  try { port.removeEventListener('message', this.__onmessage_wrapped); } catch (_) {}
                }
                this.__onmessage_wrapped = wrapped;
                port.addEventListener('message', wrapped);
              }
            },
          });
          if (typeof port.start === 'function') {
            try { port.start(); } catch (_) {}
          }
        }
        return worker;
      };
      PatchedSW.prototype = OrigSW.prototype;
      PatchedSW.__patched_by_tests__ = true;
      Object.defineProperty(window, 'SharedWorker', { value: PatchedSW });
    }

    console.log('[init] JS interception installed; mode=' + cfg.mode + ', constant=' + cfg.constant + ', start=' + cfg.start + ', step=' + cfg.step + ', current=' + cfg.current);
  } catch (e) {
    console.log('[init ERROR]', String(e && e.stack || e));
  }
})();
"""


def build_init_script(initial_mode: str = "untouched", constant_value: float = 0.4, start_value: float = 0.0, step_value: float = 0.1) -> str:
  """Render the INIT_SCRIPT_TEMPLATE with runtime data safely quoted."""
  return INIT_SCRIPT_TEMPLATE % {
    "initial_mode": json.dumps(initial_mode),  # quoted string in JS
    "constant_value": constant_value,          # numeric literal in JS
    "start_value": start_value,                # numeric literal in JS
    "step_value": step_value,                  # numeric literal in JS
  }


def run():
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()

    # Bridge page console to Python stdout so you can see logs immediately
    def _bind_console(page):
      page.on("console", lambda msg: print(f"[console:{msg.type}]", msg.text))

    page = context.new_page()
    _bind_console(page)

    # Install our interception before any app code runs
    page.add_init_script(build_init_script(initial_mode="untouched", constant_value=0.4, start_value=0.0, step_value=0.1))

    # Navigate to your page that creates a SharedWorker and/or WebSocket
    page.goto("http://localhost:8000", wait_until="load")
    page.wait_for_timeout(1000 * 10)

    # Runtime controls: switch interception modes/values during the test
    def set_mode(mode: str):
      page.evaluate("mode => { window.__ws_intercept__.mode = mode }", mode)

    def set_constant(val: float):
      page.evaluate("val => { window.__ws_intercept__.constant = val }", val)

    def set_series(mode: str, start: float, step: float):
      # sets mode and resets start/current/step in the page
      page.evaluate(
        "({mode, start, step}) => { const cfg = window.__ws_intercept__; cfg.mode = mode; cfg.start = start; cfg.step = step; cfg.current = start; }",
        {"mode": mode, "start": start, "step": step},
      )

    def set_increasing(start: float, step: float):
      set_series("increasing", start, step)

    def set_decreasing(start: float, step: float):
      set_series("decreasing", start, step)

    # Examples: switch modes at runtime
    set_mode("untouched")
    page.wait_for_timeout(10000)

    set_constant(0.4)
    set_mode("constant")
    page.wait_for_timeout(10000)

    set_increasing(start=0.0, step=0.2)
    page.wait_for_timeout(10000)

    set_decreasing(start=5.0, step=0.5)
    page.wait_for_timeout(10000)

    # Keep the browser open for manual verification
    browser.close()


if __name__ == "__main__":
  run()
