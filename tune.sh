#!/bin/bash
# Wrapper script to run the tuner CLI
cd "$(dirname "$0")"
export PYTHONPATH=src
exec python3 -m tuner.cli "$@"
