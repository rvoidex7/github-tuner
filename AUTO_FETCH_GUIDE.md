# Auto-Fetch Feature Guide

## Overview

The auto-fetch feature automatically discovers and scrapes random GitHub commits without needing to manually specify URLs.

## How It Works

### Discovery Modes

#### 1. Random Mode (default)
Discovers commits from random repositories matching criteria:
- Searches GitHub for repos by language and topic
- Fetches recent commits from found repositories
- Randomizes selection for variety

```bash
./scraper.sh auto-fetch --count 10 --language python --topic web --token YOUR_TOKEN
```

#### 2. Popular Mode
Fetches from a curated list of major open-source projects:
- Linux kernel
- Python (CPython)
- Node.js
- Rust
- VS Code
- React
- And more...

```bash
./scraper.sh auto-fetch --count 20 --mode popular --token YOUR_TOKEN
```

## Usage Examples

### Basic Auto-Fetch
```bash
# Fetch 10 random commits (random language/topic)
./scraper.sh auto-fetch --count 10 --token YOUR_TOKEN
```

### Filtered Auto-Fetch
```bash
# Python web projects
./scraper.sh auto-fetch --count 15 --language python --topic web --token YOUR_TOKEN

# JavaScript projects
./scraper.sh auto-fetch --count 20 --language javascript --token YOUR_TOKEN

# Rust projects with CLI topic
./scraper.sh auto-fetch --count 10 --language rust --topic cli --token YOUR_TOKEN
```

### Popular Repositories
```bash
# Fetch from major projects
./scraper.sh auto-fetch --count 50 --mode popular --token YOUR_TOKEN
```

### Without Token (Not Recommended)
```bash
# Limited to ~3-5 commits before hitting rate limit
./scraper.sh auto-fetch --count 3
```

## Available Filters

### Languages
- python, javascript, typescript, java, go, rust
- ruby, php, c, cpp, csharp, swift, kotlin

### Topics
- web, api, cli, tool, library, framework
- machine-learning, data-science, game, mobile

**Tip**: If not specified, a random language and topic are chosen automatically!

## Rate Limits & Best Practices

### GitHub API Rate Limits
- **Without token**: 60 requests/hour (❌ not enough for auto-fetch)
- **With token**: 5,000 requests/hour (✅ recommended)

### Recommendations
1. **Always use a token** for auto-fetch
2. Start with small counts (10-20) to test
3. Use `--mode popular` for higher quality emails
4. Run during off-peak hours for better performance

### Creating a GitHub Token
1. Go to: https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `public_repo` (read access to public repos)
4. Copy the token and use with `--token`

## Output Example

```bash
$ ./scraper.sh auto-fetch --count 5 --token ghp_xxxxx

🚀 Auto-fetching 5 patches (mode: random)

🔍 Searching repos: language=python, topic=web
✓ Found 10 repositories

📥 Fetching: https://github.com/django/django/commit/abc123.patch
   ✓ Saved (id=1): developer@example.com (Django Developer)
📥 Fetching: https://github.com/pallets/flask/commit/def456.patch
   ⊘ Skipped: duplicate email
📥 Fetching: https://github.com/psf/requests/commit/ghi789.patch
   ✓ Saved (id=2): contributor@gmail.com (John Smith)
📥 Fetching: https://github.com/tornadoweb/tornado/commit/jkl012.patch
   ⊘ Skipped: noreply email
📥 Fetching: https://github.com/bottlepy/bottle/commit/mno345.patch
   ✓ Saved (id=3): user@domain.org (OpenSource Fan)

Summary:
  ✓ Fetched: 3
  ⊘ Skipped: 2
  ✗ Errors: 0

📊 Total emails in database: 3
```

## Troubleshooting

### "Rate limit exceeded"
- You're hitting GitHub's API limits
- Solution: Use a token with `--token`
- Or wait an hour and try again

### "No repos found"
- The language/topic combination yielded no results
- Try different filters or use `--mode popular`

### Many "noreply" skips
- Normal! Many commits use GitHub's noreply email
- The scraper filters these automatically

### Slow performance
- Normal for large counts (50+)
- Each commit requires 2-3 API calls
- Be patient or reduce `--count`

## Advanced Usage

### Batch Processing
```bash
# Run multiple auto-fetches with different filters
./scraper.sh auto-fetch --count 10 --language python --token TOKEN
./scraper.sh auto-fetch --count 10 --language javascript --token TOKEN
./scraper.sh auto-fetch --count 10 --language rust --token TOKEN
```

### Monitoring Progress
The CLI shows real-time progress:
- 📥 = Fetching URL
- ✓ = Successfully saved
- ⊘ = Skipped (duplicate or noreply)
- ✗ = Error occurred

### Database Management
```bash
# Check total collected
./scraper.sh list-patches --limit 100

# View database directly
sqlite3 data/patches.db "SELECT COUNT(*) FROM patches;"
```

## Future Enhancements

Ideas for expansion:
- [ ] Save discovered URLs to file for later processing
- [ ] Resume from interruption
- [ ] Export emails to CSV
- [ ] Web UI for configuration
- [ ] Scheduled auto-fetch with cron
- [ ] Multiple GitHub token rotation
