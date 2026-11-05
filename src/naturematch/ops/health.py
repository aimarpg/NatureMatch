import shutil
import subprocess


def pi_health() -> dict:
    def vc(*a):
        try:
            return subprocess.check_output(["vcgencmd", *a], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    return {"cpu_temp": vc("measure_temp"), "throttled": vc("get_throttled"),
            "disk_free_gb": round(shutil.disk_usage("/").free / 1e9, 1)}
