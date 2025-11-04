# GitHub .patch Email Scraper

A Python tool for extracting email addresses and usernames from GitHub `.patch` URLs.

## Features

- ✅ Extracts email and username from line 2 of .patch files
- ✅ **Automatic discovery** of random GitHub commits
- ✅ Skips noreply emails automatically
- ✅ Deduplicates by email (skips if already in database)
- ✅ Async HTTP fetching with retry logic
- ✅ SQLite storage for collected emails
- ✅ CLI interface with Typer
- ✅ Unit tests

## Quick Start

### 1. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

Or use the quick start script:

```bash
./quickstart.sh
```

### 2. Fetch a .patch URL

```bash
./scraper.sh fetch https://github.com/owner/repo/pull/123.patch
```

Or with full python command:

```bash
PYTHONPATH=src python3 -m scraper.cli fetch https://github.com/owner/repo/pull/123.patch
```

With authentication (recommended to avoid rate limits):

```bash
./scraper.sh fetch https://github.com/owner/repo/pull/123.patch --token YOUR_GITHUB_TOKEN
```

### 3. Auto-fetch random commits (NEW!)

Automatically discover and scrape random GitHub commits:

```bash
# Fetch 10 random commits
./scraper.sh auto-fetch --count 10 --token YOUR_GITHUB_TOKEN

# Fetch from popular repositories
./scraper.sh auto-fetch --count 20 --mode popular --token YOUR_TOKEN

# Filter by language and topic
./scraper.sh auto-fetch --count 15 --language python --topic web --token YOUR_TOKEN
```

**Note**: Token is highly recommended for auto-fetch to avoid rate limits!

### 4. List collected emails

```bash
./scraper.sh list-patches
```

## How It Works

### Manual Fetch
Fetch specific .patch URLs directly.

### Auto-Fetch (Automatic Discovery)
The scraper can automatically discover random commits from GitHub:

1. **Random Mode**: Searches GitHub for repos by language/topic, then fetches recent commits
2. **Popular Mode**: Fetches from a curated list of popular repositories (Linux, Python, Node.js, etc.)

The scraper extracts information from line 2 of GitHub .patch files, which has this format:

```
From: username <email@domain.com>
```

### Filtering Rules

1. **Skip if email exists**: Emails are deduplicated automatically
2. **Skip noreply emails**: Any email containing "noreply" is skipped
3. **Extract only line 2**: Only the author information from line 2 is stored

## Storage

Data is stored in `data/patches.db` (SQLite) with this simple schema:

| Column     | Type    | Description                    |
|------------|---------|--------------------------------|
| id         | INTEGER | Primary key                    |
| email      | TEXT    | Email address (unique)         |
| username   | TEXT    | Username/display name          |
| created_at | TEXT    | ISO 8601 timestamp             |

## Example Output

### Manual Fetch
```bash
$ ./scraper.sh fetch https://github.com/psf/requests/pull/6000.patch

Fetching https://github.com/psf/requests/pull/6000.patch...
✓ Saved to database (id=1)
  Email: developer@example.com
  Username: John Doe
```

### Auto-Fetch
```bash
$ ./scraper.sh auto-fetch --count 5 --token YOUR_TOKEN

🚀 Auto-fetching 5 patches (mode: random)

🔍 Searching repos: language=python, topic=web
✓ Found 10 repositories

📥 Fetching: https://github.com/owner/repo/commit/abc123.patch
   ✓ Saved (id=1): dev@example.com (developer)
📥 Fetching: https://github.com/owner2/repo2/commit/def456.patch
   ⊘ Skipped: noreply email
📥 Fetching: https://github.com/owner3/repo3/commit/ghi789.patch
   ✓ Saved (id=2): user@domain.com (username)

Summary:
  ✓ Fetched: 2
  ⊘ Skipped: 1
  ✗ Errors: 0

📊 Total emails in database: 2
```

Skipping scenarios:

```bash
# Noreply email
⊘ Skipped: noreply email (noreply@github.com)

# Duplicate email
⊘ Skipped: email already in database (developer@example.com)
```

## Running Tests

```bash
PYTHONPATH=src pytest -v
```

Or quick run:

```bash
PYTHONPATH=src pytest -q
```

## Tech Stack

- **Python 3.9+** with async/await
- **httpx** - Async HTTP client with retry logic
- **Typer + Rich** - Modern CLI with beautiful output
- **SQLite** - Embedded database
- **pytest** - Testing framework

## Architecture

```
src/scraper/
├── fetcher.py   # Async HTTP client with retry logic
├── parser.py    # Line 2 email/username extraction
├── storage.py   # SQLite storage with deduplication
├── discover.py  # GitHub API for auto-discovery (NEW!)
└── cli.py       # CLI interface
```

## Rate Limits

GitHub has rate limits:
- **Unauthenticated**: 60 requests/hour (not recommended for auto-fetch)
- **Authenticated**: 5,000 requests/hour

**Always use `--token` for auto-fetch** to avoid hitting limits quickly!

## Example Script

See `examples/fetch_example.py` for a complete working example:

```bash
python3 examples/fetch_example.py
```

## Next Steps

- Add batch processing (read URLs from a file)
- Add worker queue for large-scale scraping
- Export to CSV/JSON
- Add web UI for browsing collected emails
- Deploy as a Docker container

## License

MIT
