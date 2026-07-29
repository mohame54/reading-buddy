#!/bin/sh
set -e
if [ ! -f models/stt_ar_ctc.onnx ] && [ -n "$FOLDER_DRIVE_ID" ]; then
  python download_model.py
fi
exec python -m uvicorn main:app --host 0.0.0.0 --port 8080 --loop uvloop
