#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update && sudo apt-get install -y python3-venv git docker.io docker-compose-plugin
python3 -m venv .venv && .venv/bin/pip install -e ".[pi]"
cp -n .env.example .env && cp -n config/station.example.yaml config/station.yaml
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now naturematch-api naturematch-station
