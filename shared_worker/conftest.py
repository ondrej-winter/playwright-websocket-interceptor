import pytest
import json

INIT_SCRIPT_TEMPLATE = r"""
(() => {
  try {
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
          return null;
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
      if (target === null) return data;
      if (data && typeof data === 'object') {
        if (Object.prototype.hasOwnProperty.call(data, 'value')) {
          return { ...data, value: target };
        }
        if (data.payload && typeof data.payload === 'object' &&
            Object.prototype.hasOwnProperty.call(data.payload, 'value')) {
          return { ...data, payload: { ...data.payload, value: target } };
        }
        return data;
      }
      if (typeof data === 'string' && data.includes('"value"')) {
        try {
          const obj = JSON.parse(data);
          if (obj && typeof obj === 'object') {
            if (Object.prototype.hasOwnProperty.call(obj, 'value')) {
              obj.value = target;
              return JSON.stringify(obj);
            }
            if (obj.payload && typeof obj.payload === 'object' &&
                Object.prototype.hasOwnProperty.call(obj.payload, 'value')) {
              obj.payload.value = target;
              return JSON.stringify(obj);
            }
          }
        } catch (_) {}
      }
      return data;
    };

    // Patch WebSocket
    const OrigWS = window.WebSocket;
    if (OrigWS && !OrigWS.__patched_by_tests__) {
      const PatchedWS = function(url, protocols) {
        const ws = new OrigWS(url, protocols);
        const origAdd = ws.addEventListener.bind(ws);
        ws.addEventListener = function(type, listener, options) {
          if (type === 'message' && typeof listener === 'function') {
            const wrapped = function(ev) {
              const mutatedData = mutateValueField(ev && ev.data);
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

    // Patch SharedWorker
    const OrigSW = window.SharedWorker;
    if (OrigSW && !OrigSW.__patched_by_tests__) {
      const PatchedSW = function(...args) {
        const worker = new OrigSW(...args);
        const port = worker.port;
        if (port) {
          const origAdd = port.addEventListener.bind(port);
          port.addEventListener = function(type, listener, options) {
            if (type === 'message' && typeof listener === 'function') {
              const wrapped = function(ev) {
                const mutatedData = mutateValueField(ev && ev.data);
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
  } catch (e) {
    console.log('[init ERROR]', String(e && e.stack || e));
  }
})();
"""


def build_init_script(
    initial_mode: str = "untouched",
    constant_value: float = 0.4,
    start_value: float = 0.0,
    step_value: float = 0.1,
) -> str:
    """Render the INIT_SCRIPT_TEMPLATE with runtime data safely quoted."""
    return INIT_SCRIPT_TEMPLATE % {
        "initial_mode": json.dumps(initial_mode),
        "constant_value": constant_value,
        "start_value": start_value,
        "step_value": step_value,
    }


@pytest.fixture(autouse=True, scope="function")
def install_ws_interceptor(page):
    """Automatically inject WS/SharedWorker interception script before page code runs."""
    page.add_init_script(
        build_init_script(
            initial_mode="untouched",
            constant_value=0.4,
            start_value=0.0,
            step_value=0.1,
        )
    )
    yield
