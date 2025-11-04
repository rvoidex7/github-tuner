#!/usr/bin/env python3
"""
Demo: Test the discovery module (requires httpx to be installed)
Run: python3 demo_autofetch.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from scraper.discover import GitHubDiscovery
except ImportError as e:
    print(f"❌ Error: {e}")
    print("\nPlease install dependencies first:")
    print("  python3 -m pip install -r requirements.txt")
    sys.exit(1)


def demo_discovery():
    """Demo the GitHubDiscovery class."""
    print("🔍 GitHub Discovery Demo\n")
    
    # Test URL generation
    discovery = GitHubDiscovery()
    url = discovery.generate_patch_url("torvalds", "linux", "abc123def456")
    print(f"✓ Generated patch URL:")
    print(f"  {url}")
    print()
    
    # Test language/topic lists
    print(f"✓ Available languages: {len(GitHubDiscovery.LANGUAGES)}")
    print(f"  Examples: {', '.join(GitHubDiscovery.LANGUAGES[:5])}")
    print()
    
    print(f"✓ Available topics: {len(GitHubDiscovery.TOPICS)}")
    print(f"  Examples: {', '.join(GitHubDiscovery.TOPICS[:5])}")
    print()
    
    print("💡 To test live discovery (requires internet + GitHub token):")
    print("   ./scraper.sh auto-fetch --count 5 --token YOUR_TOKEN")
    print()
    print("💡 To test without token (limited rate):")
    print("   ./scraper.sh auto-fetch --count 3")


if __name__ == "__main__":
    demo_discovery()
