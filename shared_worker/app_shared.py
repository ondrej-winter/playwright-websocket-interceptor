# app.py
import asyncio
import math
import time
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

app = FastAPI()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    t0 = time.time()
    try:
        while True:
            t = time.time() - t0
            value = 1.0 * math.sin(t * 2 * 3.1415 / 5)
            await ws.send_json({"ts": time.time(), "value": value})
            await asyncio.sleep(2)
    except Exception:
        pass


@app.get("/")
def index():
    html = """
    <!doctype html>
    <html>
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>WS via SharedWorker</title>
        <style>
          body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, \"Apple Color Emoji\", \"Segoe UI Emoji\"; margin: 2rem; }
          .value { font-size: 2rem; font-variant-numeric: tabular-nums; }
          .status { margin-bottom: 1rem; }
          .log { margin-top: 1rem; max-height: 40vh; overflow: auto; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace; font-size: 0.9rem; }
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      </head>
      <body>
        <h1>WebSocket feed via SharedWorker</h1>
        <div class=\"status\">Status: <span id=\"status\">connecting…</span></div>
        <div>Current value: <span class=\"value\" id=\"value\">—</span></div>
        <div style="margin-top:1rem;">
          <canvas id="chart" width="800" height="320"></canvas>
        </div>
        <pre class=\"log\" id=\"log\"></pre>
        <script>
          // Connect to the SharedWorker which multiplexes a single WS across tabs.
          const worker = new SharedWorker('/shared-worker.js', { name: 'ws-shared' });
          const port = worker.port;
          port.start();

          const statusEl = document.getElementById('status');
          const valueEl = document.getElementById('value');
          const logEl = document.getElementById('log');

          // --- Chart.js setup ---
          const chartEl = document.getElementById('chart');
          const chart = new Chart(chartEl, {
            type: 'line',
            data: {
              labels: [],
              datasets: [{
                label: 'WS value',
                data: [],
                borderWidth: 2,
                tension: 0.2,
                pointRadius: 0
              }]
            },
            options: {
              animation: false,
              responsive: true,
              maintainAspectRatio: false,
              scales: {
                x: { display: false },
                y: { beginAtZero: false }
              },
              plugins: { legend: { display: false } }
            }
          });

          function log(line){
            const ts = new Date().toISOString();
            logEl.textContent += `[${ts}] ${line}\n`;
            logEl.scrollTop = logEl.scrollHeight;
          }

          const MAX_POINTS = 200;

          port.onmessage = (ev) => {
            const msg = ev.data;
            if (!msg) return;
            if (msg.type === 'ready') {
              statusEl.textContent = 'ready';
              // Provide origin so worker can build ws:// URL
              port.postMessage({ type: 'init', origin: location.origin });
              port.postMessage({ type: 'connect' });
              return;
            }
            if (msg.type === 'status') {
              statusEl.textContent = msg.status;
              return;
            }
            if (msg.type === 'data') {
              const { ts, value } = msg.payload || {};
              if (typeof value === 'number') {
                valueEl.textContent = value.toFixed(5);
                // Append to chart
                chart.data.labels.push(ts ? new Date(ts).toLocaleTimeString() : '');
                chart.data.datasets[0].data.push(value);
                // Keep chart to MAX_POINTS
                if (chart.data.labels.length > MAX_POINTS) {
                  chart.data.labels.shift();
                  chart.data.datasets[0].data.shift();
                }
                chart.update();
              }
              log(`data: ${JSON.stringify(msg.payload)}`);
              return;
            }
            if (msg.type === 'closed') {
              statusEl.textContent = 'closed';
              return;
            }
            if (msg.type === 'error') {
              statusEl.textContent = 'error';
              log('error: ' + msg.error);
              return;
            }
          };

          window.addEventListener('beforeunload', () => {
            try { port.postMessage({ type: 'disconnect' }); } catch {}
          });
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get("/shared-worker.js")
def shared_worker_js():
    js = r"""
// shared-worker.js (served from FastAPI)
// One SharedWorker holds a single WebSocket to the backend and broadcasts
// messages to all connected tabs (MessagePort clients).

let ports = [];
let socket = null;
let originBase = null; // e.g., https://localhost:8000

function broadcast(msg) {
  for (const p of ports) {
    try { p.postMessage(msg); } catch (e) {}
  }
}

function openSocket() {
  if (!originBase || socket) return;
  const wsUrl = originBase.replace(/^http/, 'ws') + '/ws';
  try {
    socket = new WebSocket(wsUrl);
    broadcast({ type: 'status', status: 'connecting' });

    socket.onopen = () => {
      broadcast({ type: 'status', status: 'connected' });
    };

    socket.onmessage = (ev) => {
      let payload = null;
      try { payload = JSON.parse(ev.data); } catch { payload = ev.data; }
      broadcast({ type: 'data', payload });
    };

    socket.onerror = (err) => {
      broadcast({ type: 'error', error: String(err && err.message || 'socket error') });
    };

    socket.onclose = () => {
      broadcast({ type: 'closed' });
      socket = null;
      // Optional: simple retry
      setTimeout(() => {
        if (ports.length) openSocket();
      }, 1000);
    };
  } catch (e) {
    broadcast({ type: 'error', error: String(e && e.message || e) });
  }
}

onconnect = function (e) {
  const port = e.ports[0];
  ports.push(port);
  port.start();
  port.postMessage({ type: 'ready' });

  port.onmessage = (event) => {
    const msg = event.data || {};
    if (msg.type === 'init' && msg.origin) {
      // Remember the origin to build ws URL
      if (!originBase) originBase = msg.origin;
    }
    if (msg.type === 'connect') {
      if (!socket) openSocket();
    }
    if (msg.type === 'disconnect') {
      // Client is going away; remove its port
      const idx = ports.indexOf(port);
      if (idx !== -1) ports.splice(idx, 1);
      // If no clients remain, close the socket to conserve resources
      if (!ports.length && socket) {
        try { socket.close(); } catch {}
        socket = null;
      }
    }
  };

  port.onclose = () => {
    const idx = ports.indexOf(port);
    if (idx !== -1) ports.splice(idx, 1);
    if (!ports.length && socket) {
      try { socket.close(); } catch {}
      socket = null;
    }
  };
};
"""
    return Response(content=js, media_type="application/javascript")


app.mount("/static", StaticFiles(directory="static"), name="static")
