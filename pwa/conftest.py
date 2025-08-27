# conftest.py
import pytest

INIT_SCRIPT = r"""
(() => {
  try {
    if (window.__ws_logger_installed__) return;
    window.__ws_logger_installed__ = true;

    const logPrefix = "[ws-interceptor]";
    const td = new TextDecoder();

    const logData = (tag, data) => {
      // Pretty print strings/JSON, support Blob/ArrayBuffer
      const print = (txtOrObj) => console.log(`${logPrefix} ${tag}:`, txtOrObj);
      try {
        if (typeof data === "string") {
          try { print(JSON.parse(data)); } catch { print(data); }
          return;
        }
        if (data instanceof Blob) {
          data.text().then(t => { try { print(JSON.parse(t)); } catch { print(t); } });
          return;
        }
        if (data instanceof ArrayBuffer) {
          const t = td.decode(new Uint8Array(data));
          try { print(JSON.parse(t)); } catch { print(t); }
          return;
        }
      } catch {}
      print(data);
    };

    // -------- WebSocket logging (constructor patch) --------
    const OrigWS = window.WebSocket;
    if (OrigWS && !OrigWS.__logged__) {
      const PatchedWS = function(url, protocols) {
        const ws = new OrigWS(url, protocols);

        // Log outgoing
        const origSend = ws.send;
        ws.send = function(data) {
          logData("send", data);
          return origSend.call(this, data);
        };

        // Log incoming for addEventListener
        const origAdd = ws.addEventListener.bind(ws);
        ws.addEventListener = function(type, listener, options) {
          if (type === "message" && typeof listener === "function") {
            const wrapped = (ev) => { logData("recv", ev.data); return listener.call(this, ev); };
            return origAdd(type, wrapped, options);
          }
          return origAdd(type, listener, options);
        };

        // Log incoming for onmessage
        Object.defineProperty(ws, "onmessage", {
          configurable: true,
          enumerable: true,
          get() { return this.__onmessage_original || null; },
          set(fn) {
            this.__onmessage_original = fn;
            if (typeof fn === "function") {
              const wrapped = (ev) => { logData("recv", ev.data); return fn.call(ws, ev); };
              // ensure we don't double-attach
              if (this.__onmessage_wrapped) {
                try { ws.removeEventListener("message", this.__onmessage_wrapped); } catch {}
              }
              this.__onmessage_wrapped = wrapped;
              ws.addEventListener("message", wrapped);
            }
          },
        });

        return ws;
      };
      PatchedWS.prototype = OrigWS.prototype;
      PatchedWS.__logged__ = true;
      Object.defineProperty(window, "WebSocket", { value: PatchedWS });
      console.log(`${logPrefix} active: logging WS send/recv`);
    }

    // -------- SharedWorker port logging (if app uses a worker) --------
    const OrigSW = window.SharedWorker;
    if (OrigSW && !OrigSW.__logged__) {
      const PatchedSW = function(...args) {
        const worker = new OrigSW(...args);
        const port = worker.port;
        if (port) {
          const origPost = port.postMessage;
          port.postMessage = function(data, ...rest) {
            logData("port->postMessage", data);
            return origPost.call(this, data, ...rest);
          };

          const origAdd = port.addEventListener.bind(port);
          port.addEventListener = function(type, listener, options) {
            if (type === "message" && typeof listener === "function") {
              const wrapped = (ev) => { logData("port<-message", ev.data); return listener.call(this, ev); };
              return origAdd(type, wrapped, options);
            }
            return origAdd(type, listener, options);
          };

          Object.defineProperty(port, "onmessage", {
            configurable: true,
            enumerable: true,
            get() { return this.__onmessage_original || null; },
            set(fn) {
              this.__onmessage_original = fn;
              if (typeof fn === "function") {
                const wrapped = (ev) => { logData("port<-message", ev.data); return fn.call(port, ev); };
                if (this.__onmessage_wrapped) {
                  try { port.removeEventListener("message", this.__onmessage_wrapped); } catch {}
                }
                this.__onmessage_wrapped = wrapped;
                port.addEventListener("message", wrapped);
              }
            },
          });

          if (typeof port.start === "function") { try { port.start(); } catch {} }
        }
        return worker;
      };
      PatchedSW.prototype = OrigSW.prototype;
      PatchedSW.__logged__ = true;
      Object.defineProperty(window, "SharedWorker", { value: PatchedSW });
      console.log(`${logPrefix} active: logging SharedWorker port messages`);
    }
  } catch (e) {
    console.log("[init ERROR]", String(e && e.stack || e));
  }
})();
"""

@pytest.fixture(autouse=True, scope="function")
def install_ws_logger(page):
    page.add_init_script(INIT_SCRIPT)
    yield
