#!/bin/bash
set -e

cleanup() {
    kill $MCP_PID $FASTAPI_PID 2>/dev/null || true
    wait
}

trap cleanup SIGTERM SIGINT

# Start MCP server as background process
python -m worker.mcp_server &
MCP_PID=$!

# Start FastAPI as foreground process
uvicorn worker.main:app --host 0.0.0.0 --port 3000 &
FASTAPI_PID=$!

# Wait for either to exit
wait -n $MCP_PID $FASTAPI_PID 2>/dev/null || true
cleanup
