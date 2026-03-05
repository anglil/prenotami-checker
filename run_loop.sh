#!/bin/bash
# PrenotaMi Slot Checker - Background Runner
# Runs the checker every 15 minutes in the background.
#
# Usage:
#   Start: nohup ./run_loop.sh &
#   Stop:  kill $(cat .runner.pid)
#   Logs:  tail -f logs/checker.log

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Save PID for easy stopping
echo $$ > .runner.pid

echo "[$(date)] PrenotaMi checker loop started (PID: $$)"
echo "[$(date)] Checking every 15 minutes..."
echo "[$(date)] To stop: kill $(cat .runner.pid)"

while true; do
    echo "[$(date)] Running check..."
    source venv/bin/activate
    python3 checker.py
    echo "[$(date)] Next check in 15 minutes..."
    sleep 900
done
