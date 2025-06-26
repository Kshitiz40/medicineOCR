#!/usr/bin/env bash
set -o errexit

# Try to install libzbar0 (may not work on Render's default environment)
sudo apt-get update && sudo apt-get install -y libzbar0 || echo "Warning: Failed to install libzbar0"

pip install -r requirements.txt
