#!/bin/bash
# Run Python backend
cd "$(dirname "$0")"
python3 -m uvicorn main:asgi_app --host 0.0.0.0 --port ${PORT:-3001}
