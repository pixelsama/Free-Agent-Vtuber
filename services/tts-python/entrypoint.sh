#!/bin/bash
set -e

# Fix permissions for shared volume
sudo chown -R app:app /tmp/aivtuber_tasks
sudo chmod -R 755 /tmp/aivtuber_tasks

# Start the application
exec python main.py