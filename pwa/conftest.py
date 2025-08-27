# conftest.py
import pytest
import json

INIT_SCRIPT_TEMPLATE = r"""
(() => {
  try {
    // Runtime config (tweak from tests via page.evaluate)
    window.__ws_intercept__ = window.__ws_intercept__ || {
      // value generator
      mode: %(initial_mode)s,           // "untouched" | "constant" | "increasing" | "decreasing"
      constant: %(constant_value)s,
      start: %(start_value)s,
      step: %(step_value)s,
      current: %(start_value)s,

      // domain-specific rewrite for instrument "GOLDm#"
      targetSymbol: %(target_symbol)s,  // e.g. "GOLDm#"
      baMode: "same",                   // "same" | "spread"
      spreadDelta: 5                    // used when baMode === "spread"
    };
    const cfg = window.__ws_intercept__;

    const nextValue = () => {
      switch (cfg.mode) {
        case "untouched":   return null; // do not mutate
        case "constant":    return Number(cfg.constant);
        case "increasing": {
          const v = Number(cfg.current);
          cfg.current = v + Number(cfg.step);
          return v;
        }
        case "decreasing": {
          const v = Number(cfg.current);
          cfg.current = v - Number(cfg.step);
          return v;
        }
        default: return null;
      }
    };

    // --- helpers ------------------------------------------------------------
    const setBa = (tk, target) => {
      if (!tk || !Array.isArray(tk.ba) || tk.ba.length < 2) return false;
      const t = Number(target);
      if (cfg.baMode === "spread") {
        const d = Number(cfg.spreadDelta || 0);
        tk.ba = [t - d, t + d];
      } else {
        tk.ba = [t, t];
      }
      return true;
    };

    // Supports both shapes:
    //  A) {"messages":[{"tk":{ "sl":"GOLDm#", "ba":[..] }, ...}]}
    //  B) {"messages":[{"ts":{"tk":{ "sl":"GOLDm#", "ba":[..] }, ...}, ...}]}
    const rewriteBaForSymbol = (obj, target) => {
      if (!obj || typeof obj !== "object") return false;

      let changed = false;
      const sym = String(cfg.targetSymbol);

      const msgs = obj.messages;
      if (Array.isArray(msgs)) {
        for (const m of msgs) {
          // direct under m.tk
          if (m && m.tk && m.tk.sl === sym) {
            if (setBa(m.tk, target)) changed = true;
          }
          // nested under m.ts.tk  (your provided format)
          const tsTk = m && m.ts && m.ts.tk;
          if (tsTk && tsTk.sl === sym) {
            if (setBa(tsTk, target)) changed = true;
          }
        }
      }
      return changed;
    };

    const mutateValueField = (data) => {
      const target = nextValue();
      if (target === null) return data; // untouched pass-through

      // --- Case A: structured object directly --------------------------------
      if (data && typeof data === "object") {
        // Keep the generic "value" rewrite for backward compatibility
        if (Object.prototype.hasOwnProperty.call(data, "value")) {
          return { ...data, value: target };
        }
        if (data.payload && typeof data.payload === "object" &&
            Object.prototype.hasOwnProperty.call(data.payload, "value")) {
          return { ...data, payload: { ...data.payload, value: target } };
        }

        // Domain-specific GOLDm# ba rewrite
        const clone = JSON.parse(JSON.stringify(data));
        const changed = rewriteBaForSymbol(clone, target);
        return changed ? clone : data;
      }

      // --- Case B: JSON string ------------------------------------------------
      if (typeof data === "string") {
        try {
          const obj = JSON.parse(data);

          // Generic "value" rewrite
          let touched = false;
          if (obj && typeof obj === "object") {
            if (Object.prototype.hasOwnProperty.call(obj, "value")) {
              obj.value = target;
              touched = true;
            } else if (obj.payload && typeof obj.payload === "object" &&
                       Object.prototype.hasOwnProperty.call(obj.payload, "value")) {
              obj.payload.value = target;
              touched = true;
            }
          }

          // Domain-specific GOLDm# ba rewrite (handles m.ts.tk as in your sample)
          if (rewriteBaForSymbol(obj, target)) touched = true;

          if (touched) return JSON.stringify(obj);
        } catch (_) { /* ignore parse errors */ }
      }

      // --- Fallback -----------------------------------------------------------
      return data;
    };

    // --- Patch WebSocket -----------------------------------------------------
    const OrigWS = window.WebSocket;
    if (OrigWS && !OrigWS.__patched_by_tests__) {
      const PatchedWS = function(url, protocols) {
        const ws = new OrigWS(url, protocols);
        const origAdd = ws.addEventListener.bind(ws);
        ws.addEventListener = function(type, listener, options) {
          if (type === "message" && typeof listener === "function") {
            const wrapped = function(ev) {
              const mutatedData = mutateValueField(ev && ev.data);
              const newEv = new MessageEvent("message", { data: mutatedData });
              return listener.call(this, newEv);
            };
            return origAdd(type, wrapped, options);
          }
          return origAdd(type, listener, options);
        };
      Object.defineProperty(ws, "onmessage", {
          configurable: true,
          enumerable: true,
          get() { return this.__onmessage_original || null; },
          set(fn) {
            this.__onmessage_original = fn;
            if (typeof fn === "function") {
              const wrapped = (ev) => {
                const mutatedData = mutateValueField(ev && ev.data);
                const newEv = new MessageEvent("message", { data: mutatedData });
                return fn.call(ws, newEv);
              };
              if (this.__onmessage_wrapped) {
                try { ws.removeEventListener("message", this.__onmessage_wrapped); } catch(_) {}
              }
              this.__onmessage_wrapped = wrapped;
              ws.addEventListener("message", wrapped);
            }
          },
        });
        return ws;
      };
      PatchedWS.prototype = OrigWS.prototype;
      PatchedWS.__patched_by_tests__ = true;
      Object.defineProperty(window, "WebSocket", { value: PatchedWS });
    }

    // --- Patch SharedWorker Port ---------------------------------------------
    const OrigSW = window.SharedWorker;
    if (OrigSW && !OrigSW.__patched_by_tests__) {
      const PatchedSW = function(...args) {
        const worker = new OrigSW(...args);
        const port = worker.port;
        if (port) {
          const origAdd = port.addEventListener.bind(port);
          port.addEventListener = function(type, listener, options) {
            if (type === "message" && typeof listener === "function") {
              const wrapped = function(ev) {
                const mutatedData = mutateValueField(ev && ev.data);
                const newEv = new MessageEvent("message", { data: mutatedData });
                return listener.call(this, newEv);
              };
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
                const wrapped = (ev) => {
                  const mutatedData = mutateValueField(ev && ev.data);
                  const newEv = new MessageEvent("message", { data: mutatedData });
                  return fn.call(port, newEv);
                };
                if (this.__onmessage_wrapped) {
                  try { port.removeEventListener("message", this.__onmessage_wrapped); } catch(_) {}
                }
                this.__onmessage_wrapped = wrapped;
                port.addEventListener("message", wrapped);
              }
            },
          });
          if (typeof port.start === "function") { try { port.start(); } catch(_) {} }
        }
        return worker;
      };
      PatchedSW.prototype = OrigSW.prototype;
      PatchedSW.__patched_by_tests__ = true;
      Object.defineProperty(window, "SharedWorker", { value: PatchedSW });
    }
  } catch (e) {
    console.log("[init ERROR]", String(e && e.stack || e));
  }
})();
"""

def build_init_script(initial_mode: str = "untouched",
                      constant_value: float = 0.4,
                      start_value: float = 0.0,
                      step_value: float = 0.1,
                      target_symbol: str = "GOLDm#") -> str:
    """Render the INIT_SCRIPT_TEMPLATE with runtime data safely quoted."""
    return INIT_SCRIPT_TEMPLATE % {
        "initial_mode": json.dumps(initial_mode),
        "constant_value": constant_value,
        "start_value": start_value,
        "step_value": step_value,
        "target_symbol": json.dumps(target_symbol),
    }

@pytest.fixture(autouse=True, scope="function")
def install_ws_interceptor(page):
    """Automatically inject WS/SharedWorker interception script before page code runs."""
    page.add_init_script(build_init_script(
        initial_mode="untouched",
        constant_value=0.4,
        start_value=0.0,
        step_value=0.1,
        target_symbol="GOLDm#",
    ))
    yield