import argparse

from naturematch.common import logging as nmlog
from naturematch.common.config import load_yaml


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/station.yaml")
    cfg = load_yaml(ap.parse_args().config)
    nmlog.setup()
    # build sensors (SimulatedSensor if cfg["simulate"]), counter, LED; run loop
    print("station", cfg["station_id"])


if __name__ == "__main__":
    main()
