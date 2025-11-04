# GitHub .patch Email Scraper - Version 1.0.0

**First Stable Release** 🎉

## What's New

Version 1.0.0 introduces a complete email scraping solution for GitHub .patch files with automatic commit discovery!

### ✨ Key Features

#### Email & Username Extraction
- Extracts email addresses and usernames from line 2 of GitHub .patch files
- Format: `From: username <email@domain.com>`
- Stores data in SQLite database with automatic deduplication

#### Automatic Commit Discovery (NEW!)
- **Random Mode**: Discover commits from GitHub repos by language/topic
- **Popular Mode**: Fetch from curated list of major open-source projects (Linux, Python, Node.js, etc.)
- No manual URL hunting required!

#### Smart Filtering
- ✅ Automatic deduplication (skips existing emails)
- ✅ Skips noreply emails automatically  
- ✅ Real-time progress with beautiful CLI output

#### Robust Fetching
- Async HTTP client with retry logic
- Exponential backoff for rate limits
- GitHub token authentication support (5,000 req/hour)

## Quick Start

```bash
# Install dependencies
python3 -m pip install -r requirements.txt

# Auto-fetch 10 random commits
./scraper.sh auto-fetch --count 10 --token YOUR_GITHUB_TOKEN

# View collected emails
./scraper.sh list-patches
```

## CLI Commands

```bash
# Manual fetch
./scraper.sh fetch https://github.com/owner/repo/commit/sha.patch

# Auto-fetch random commits
./scraper.sh auto-fetch --count 10 --token YOUR_TOKEN

# Auto-fetch from popular repos  
./scraper.sh auto-fetch --count 20 --mode popular --token YOUR_TOKEN

# Filter by language/topic
./scraper.sh auto-fetch --count 15 --language python --topic web --token YOUR_TOKEN

# List collected emails
./scraper.sh list-patches
```

## What's Included

- 5 core Python modules (fetcher, parser, storage, discover, cli)
- Comprehensive CLI with Typer + Rich
- 10 unit tests (100% passing)
- Complete documentation (README, guides, quick reference)
- Example scripts and demos
- Docker support

## Documentation

- `README.md` - Quick start guide
- `AUTO_FETCH_GUIDE.md` - Comprehensive auto-fetch documentation
- `QUICKREF.md` - Command reference
- `CHANGES.md` - Change history

## Requirements

- Python 3.9+
- pip
- Internet connection
- GitHub token (recommended for auto-fetch)

## Tech Stack

- Python 3.9+ with async/await
- httpx - Async HTTP client
- Typer + Rich - Modern CLI
- SQLite - Local database
- pytest - Testing

## Rate Limits

- Without token: 60 requests/hour
- With token: 5,000 requests/hour

**Always use `--token` for auto-fetch to avoid limits!**

## Installation

```bash
git clone https://github.com/Ru1vly/github-mail-scraper.git
cd github-mail-scraper
python3 -m pip install -r requirements.txt
./scraper.sh --help
```

## Get a GitHub Token

1. Visit: https://github.com/settings/tokens
2. Generate new token (classic)
3. Select scope: `public_repo`
4. Copy token and use with `--token`

## Statistics

- **Lines of Code**: 1,200+
- **Modules**: 5
- **Tests**: 10 (100% passing)
- **Supported Languages**: 13
- **Supported Topics**: 10
- **Popular Repos**: 10

## License

MIT License

---

**Full Changelog**: https://github.com/Ru1vly/github-mail-scraper/commits/v1.0.0
