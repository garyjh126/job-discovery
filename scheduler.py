"""Run daily.py once a day, at or after RUN_HOUR local time, inside the job-discovery container.

Checks every 10 minutes, so a run missed while the Mac was off or asleep happens as soon as
Docker is running again. A day counts as done once data/runs/<date>.json exists.
"""
import datetime, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_HOUR = int(os.environ.get("RUN_HOUR", "8"))

while True:
    now = datetime.datetime.now()
    run_file = os.path.join(HERE, "data", "runs", f"{now.date().isoformat()}.json")
    if now.hour >= RUN_HOUR and not os.path.exists(run_file):
        print(f"{now:%Y-%m-%d %H:%M} running daily sweep", flush=True)
        result = subprocess.run([sys.executable, "-I", os.path.join(HERE, "daily.py")])
        if result.returncode:
            print(f"daily.py failed with exit code {result.returncode}; will retry in 10 minutes", flush=True)
    time.sleep(600)
