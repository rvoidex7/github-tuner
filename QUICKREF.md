# Quick Reference

## Install
```bash
python3 -m pip install -r requirements.txt
```

## Usage
```bash
# Fetch a specific .patch URL
./scraper.sh fetch https://github.com/owner/repo/pull/123.patch

# Auto-fetch random commits (NEW!)
./scraper.sh auto-fetch --count 10 --token YOUR_TOKEN

# Auto-fetch from popular repos
./scraper.sh auto-fetch --count 20 --mode popular --token YOUR_TOKEN

# Auto-fetch with filters
./scraper.sh auto-fetch --count 15 --language python --topic web --token YOUR_TOKEN

# With token (manual fetch)
./scraper.sh fetch URL --token YOUR_TOKEN

# List collected emails
./scraper.sh list-patches

# Show help
./scraper.sh --help
./scraper.sh auto-fetch --help
```

## Test
```bash
# Test with example file
python3 test_example.py

# Run unit tests
PYTHONPATH=src pytest -v
```

## What Gets Extracted

From line 2 of .patch files:
```
From: username <email@domain.com>
       ^^^^^^^^   ^^^^^^^^^^^^^^^^^
       stored     stored (unique key)
```

## Filtering Rules

1. ✓ Skip if email exists
2. ✓ Skip noreply emails
3. ✓ Extract only line 2

## Database Location

`data/patches.db` (SQLite)

View with:
```bash
sqlite3 data/patches.db "SELECT * FROM patches;"
```
