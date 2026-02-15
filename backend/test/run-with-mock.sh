#!/bin/bash
# Run server (planner uses mock data from db/test/mock-ai)
cd "$(dirname "$0")/.."
node server.js
