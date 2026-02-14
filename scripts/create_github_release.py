#!/usr/bin/env python3
"""
Create GitHub Release with MRT data files.

Usage:
    python scripts/create_github_release.py --version 20240214 --file outputs/latest/stage3_final.json
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_repo():
    """Get current git repo name"""
    result = subprocess.run(
        ['gh', 'repo', 'view', '--json', 'nameWithOwner'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        import json
        return json.loads(result.stdout)['nameWithOwner']
    return "YOUR_USER/mrt-data"


def create_release(version: str, file_path_input: str, dry_run: bool = False):
    """Create GitHub release with data file"""
    
    file_path = Path(file_path_input)
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    # Check gh CLI
    try:
        result = subprocess.run(['gh', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: GitHub CLI (gh) not installed")
        print("Install: https://cli.github.com/")
        sys.exit(1)
    
    # Format release notes
    release_notes = f"""# MRT Data Release {version}

**Release Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

## Files
- `stage3_final.json` - Complete station data with exits and bus stops

## Data Sources
- Station coordinates: OneMap API
- Exit data: Data.gov.sg
- Enrichment: Fandom Wiki + LLM extraction

## Usage

### Direct Download
```bash
curl -L https://github.com/{get_repo()}/releases/download/{version}/stage3_final.json
```

### iOS Swift
```swift
let url = URL(string: "https://github.com/{get_repo()}/releases/download/{version}/stage3_final.json")!
```

### Check for Updates
Compare `metadata.data_version` from current vs remote file.
"""
    
    cmd = [
        'gh', 'release', 'create',
        version,
        '--title', f'MRT Data {version}',
        '--notes', release_notes,
        '--attach', str(file_path)
    ]
    
    if dry_run:
        print("Dry run - would execute:")
        print(' '.join(cmd))
        return
    
    print(f"Creating release {version}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✓ Release created: https://github.com/{get_repo()}/releases/tag/{version}")
    else:
        print(f"✗ Failed: {result.stderr}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Create GitHub Release')
    parser.add_argument('--version', '-v', required=True, help='Version (e.g., 20240214)')
    parser.add_argument('--file', '-f', required=True, help='Path to stage3_final.json')
    parser.add_argument('--dry-run', action='store_true', help='Print commands only')
    
    args = parser.parse_args()
    create_release(args.version, args.file, args.dry_run)


if __name__ == '__main__':
    main()
