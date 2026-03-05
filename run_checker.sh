#!/bin/bash
# Wrapper script for the PrenotaMi checker
# This is called by launchd

cd "$(dirname "$0")"
source venv/bin/activate
python3 checker.py
