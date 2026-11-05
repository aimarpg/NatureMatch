"""Log manual in/out key presses (i/o + Enter) to validation/results/*.csv."""
import csv
import sys
import time

with open(f"validation/results/manual_{int(time.time())}.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ts", "truth"])
    for line in sys.stdin:
        if line.strip() in ("i", "o"):
            w.writerow([time.time(), line.strip()])
            f.flush()
