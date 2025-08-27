import pytest
import json

INIT_SCRIPT_TEMPLATE = r"""
(() => {
  try {
    window.__ws_intercept__ = {
      constant: %(constant_value)s,
      spread: %(spread_value)s,
      targetSymbol: %(target_symbol)s
    };
    const cfg = window.__ws_intercept__;

    const mutateBa = (data) => {
      if (!data) return data;
      let obj;
      if (typeof data === "string") {
        try { obj = JSON.parse(data); } catch { return data; }
      } else if (typeof data === "object") {
        obj = JSON.parse(JSON.stringify(data));
      } else {
        return data;
      }

      const msgs = obj.messages;
      if (Array.isArray(msgs)) {
        for (const m of msgs) {
          const tk = m && m.ts && m.ts.tk;
          if (tk && tk.sl === cfg.targetSymbol && Array.isArray(tk.ba) && tk.ba.length >= 2) {
            const c = Number(cfg.constant);
            const s = Number(cfg.spread);
            tk.ba = [c - s, c + s];
          }
        }
      }
      return typeof data === "string" ? JSON.stringify(obj) : obj;
    };

    const OrigWS = window.WebSocket;
    if (OrigWS && !OrigWS.__patched_by_tests__) {
      const PatchedWS = function(url, protocols) {
        const ws = new OrigWS(url, protocols);
        const origAdd = ws.addEventListener.bind(ws);
        ws.addEventListener = function(type, listener, options) {
          if (type === "message" && typeof listener === "function") {
            const wrapped = function(ev) {
              const mutatedData = mutateBa(ev && ev.data);
              const newEv = new MessageEvent("message", { data: mutatedData });
              return listener.call(this, newEv);
            };
            return origAdd(type, wrapped, options);
          }
          return origAdd(type, listener, options);
        };
        return ws;
      };
      PatchedWS.prototype = OrigWS.prototype;
      PatchedWS.__patched_by_tests__ = true;
      Object.defineProperty(window, "WebSocket", { value: PatchedWS });
    }
  } catch (e) {
    console.log("[init ERROR]", String(e && e.stack || e));
  }
})();
"""


def build_init_script(
    constant_value: float = 3380.0,
    spread_value: float = 0.5,
    target_symbol: str = "GOLDm#",
) -> str:
    return INIT_SCRIPT_TEMPLATE % {
        "constant_value": constant_value,
        "spread_value": spread_value,
        "target_symbol": json.dumps(target_symbol),
    }


@pytest.fixture(autouse=True, scope="function")
def install_ws_interceptor(page):
    page.add_init_script(
        build_init_script(
            constant_value=3380.0,  # your desired mid price
            spread_value=0.5,  # half-spread
            target_symbol="GOLDm#",
        )
    )
    yield
