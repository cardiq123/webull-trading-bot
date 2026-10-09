#!/bin/sh
# Long-running sandbox watch. Replaces the once-a-minute forward-test cron.
# Do not run this and the minute cycle together. A leftover minute cycle
# takes the same lock and skips while this process is in a tick.
#
# On the box, stop the per-minute line in /workspace/vwap-runner/loop.sh
# and start this once:
#
#   cd /workspace/vwap-runner   # or the repo the runner pulls
#   WEBULL_ENV=sandbox nohup ./scripts/vwap-watch.sh >> logs/forward-watch.log 2>&1 &
#
# systemd is the same command, Restart=always, WorkingDirectory=the repo.
# The process polls every 5 seconds and runs the full signal cycle at
# :00:03, :05:03, :10:03, and so on, America/New_York.
set -eu
cd "$(dirname "$0")/.."
export WEBULL_ENV="${WEBULL_ENV:-sandbox}"
PY="${PYTHON:-python3}"
exec "$PY" -m webull_bot forward-watch \
  vwap_band_15m vwap_band_15m_qqq_aggr neckline_trapdoor_qqq "$@"
