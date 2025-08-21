Start a FastAPI application with Uvicorn
```
uvicorn app:app --reload --port 8000
```

Run tests
```
$ pytest --headed test_ws.py::test_increasing_then_decreasing
```