# app.py
import asyncio
import math
import time
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    t0 = time.time()
    try:
        while True:
            t = time.time() - t0
            value = 1.0 * math.sin(t*2*3.1415/5)
            await ws.send_json({"ts": time.time(), "value": value})
            await asyncio.sleep(2)
    except Exception:
        pass

@app.get("/")
def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")