#!/bin/bash
echo "🟢 start.sh running" > log.txt
python main.py >> log.txt 2>&1
