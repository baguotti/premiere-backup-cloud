#!/bin/bash
cd "$(dirname "$0")"

# Check if the script is already running
if pgrep -f "src/backup_prproj.py" > /dev/null; then
    echo "Backup script is already running. Exiting."
    exit 0
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "First time setup: Creating virtual environment and installing dependencies..."
    /usr/bin/python3 -m venv venv || python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

echo "Starting backup script..."
./venv/bin/python src/backup_prproj.py
