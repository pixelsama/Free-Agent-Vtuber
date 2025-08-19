#!/bin/bash
set -e

# Fix permissions for shared volume
sudo chown -R app:app /tmp/aivtuber_tasks
sudo chmod -R 755 /tmp/aivtuber_tasks

# Start the application with provided command or default to main.py
if [ $# -eq 0 ]; then
    exec python main.py
else
    exec "$@"
fi