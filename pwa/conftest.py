import pytest

INIT_JS = r"""
(() => {
  if (window.__sharedWorkerProxyInstalled__) return;
  window.__sharedWorkerProxyInstalled__ = true;

  // Runtime config (you can tweak from DevTools)
  window.__US100_cfg = Object.assign({
    symbol: "US100Cash",
    forcedBa: [950, 1050],
  }, window.__US100_cfg || {});

  // Replace SharedWorker constructor with a proxy that bootstraps the worker.
  const OrigSW = window.SharedWorker;
  if (!OrigSW) {
    console.log("[us100-proxy] No SharedWorker in this environment");
    return;
  }
  if (OrigSW.__us100Proxy__) return;

  const mkBootstrap = (origUrl, cfg) => `
    // ---- bootstrap runs INSIDE the SharedWorker global scope ----
    (function(){
      var __CFG = { symbol: ${JSON.stringify(cfg.symbol)}, forcedBa: ${JSON.stringify(cfg.forcedBa)} };

      // Deep scan: find any object with { sl: string, ba: [bid, ask] } and rewrite when sl===symbol
      function mutateUS100Deep(root){
        var changed = false, stack = [root], seen = typeof WeakSet!=="undefined" ? new WeakSet() : { has(){return false;}, add(){} };
        while (stack.length){
          var node = stack.pop();
          if (!node || typeof node !== "object") continue;
          try { if (seen.has(node)) continue; seen.add(node); } catch(e) {}
          if (typeof node.sl === "string" && Array.isArray(node.ba) && node.ba.length >= 2){
            if (node.sl === __CFG.symbol){
              node.ba[0] = __CFG.forcedBa[0];
              node.ba[1] = __CFG.forcedBa[1];
              changed = true;
            }
          }
          if (Array.isArray(node)){
            for (var i=0;i<node.length;i++) stack.push(node[i]);
          } else {
            for (var k in node) if (Object.prototype.hasOwnProperty.call(node,k)) stack.push(node[k]);
          }
        }
        return changed;
      }

      // Patch MessagePort.prototype.postMessage BEFORE importing the real worker script,
      // so even early posts during script evaluation are intercepted.
      (function(){
        var MP = self.MessagePort && self.MessagePort.prototype;
        if (!MP || MP.__us100_mutated__) return;
        var origPost = MP.postMessage;
        MP.postMessage = function(data, transfer){
          try {
            if (data && typeof data === "object"){
              mutateUS100Deep(data);
            } else if (typeof data === "string"){
              try {
                var obj = JSON.parse(data);
                if (mutateUS100Deep(obj)) data = JSON.stringify(obj);
              } catch(_){}
            }
          } catch(_){}
          return arguments.length > 1 ? origPost.call(this, data, transfer) : origPost.call(this, data);
        };
        MP.__us100_mutated__ = true;
      })();

      // Import the ORIGINAL SharedWorker script (all its code runs after our patch)
      try {
        importScripts(${JSON.stringify(origUrl)});
      } catch (e) {
        // If import fails, surface an error so you notice in DevTools
        try { console.log("[us100-proxy][worker] importScripts error:", String(e && e.message || e)); } catch(_){}
      }
    })();
  `;

  const ProxySW = function(url, options){
    try {
      // Resolve to absolute URL so importScripts works inside the worker
      const abs = new URL(url, location.href).toString();

      // Build a bootstrap script that imports the original worker and patches port.postMessage
      const code = mkBootstrap(abs, window.__US100_cfg);
      const blob = new Blob([code], { type: "application/javascript" });
      const proxiedUrl = URL.createObjectURL(blob);

      const w = new OrigSW(proxiedUrl, options);
      // Expose the underlying port exactly like the original
      return w;
    } catch (e) {
      console.log("[us100-proxy] Proxy construction failed, falling back to original:", e);
      return new OrigSW(url, options);
    }
  };
  ProxySW.prototype = OrigSW.prototype;
  Object.defineProperty(window, "SharedWorker", { configurable: true, writable: false, value: ProxySW });
  ProxySW.__us100Proxy__ = true;

  console.log("[us100-proxy] SharedWorker proxy installed; faking", window.__US100_cfg.symbol, "ba ->", window.__US100_cfg.forcedBa);
})();
"""

@pytest.fixture(autouse=True, scope="function")
def install_us100_sharedworker_proxy(page):
  page.add_init_script(INIT_JS)
  yield
