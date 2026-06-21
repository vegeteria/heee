#!/bin/bash

while true; do
    echo "Starting execution at $(date)"
    
    # 1. Run your Python script
    python3 file.py
    
    # 2. Stage changes, commit, and push
    git add .
    git commit -m "Automated update: $(date)"
    git push origin main
    
    echo "Sleeping for 5 minutes..."
    sleep 300
done
