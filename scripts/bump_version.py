#!/usr/bin/env python3
"""
Version bump script for Sandbox Manager.

Usage:
    python scripts/bump_version.py major|minor|patch

Examples:
    python scripts/bump_version.py patch  # 1.0.0 → 1.0.1
    python scripts/bump_version.py minor  # 1.0.1 → 1.1.0
    python scripts/bump_version.py major  # 1.1.0 → 2.0.0
"""
import sys
import re
from pathlib import Path


def get_current_version() -> str:
    """Get current version from __init__.py or pyproject.toml"""
    init_file = Path(__file__).parent.parent / "core" / "__init__.py"
    
    if init_file.exists():
        content = init_file.read_text()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    
    # Fallback: check if version file exists
    version_file = Path(__file__).parent.parent / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    
    return "0.1.0"  # Default if no version found


def parse_version(version: str) -> tuple:
    """Parse version string into tuple"""
    parts = version.lstrip('v').split('.')
    return tuple(int(p) for p in parts)


def bump_version(version: str, bump_type: str) -> str:
    """Bump version based on type"""
    major, minor, patch = parse_version(version)
    
    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")
    
    return f"{major}.{minor}.{patch}"


def update_version_files(new_version: str):
    """Update version in all relevant files"""
    root = Path(__file__).parent.parent
    
    # Update core/__init__.py
    init_file = root / "core" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text()
        content = re.sub(
            r'(__version__\s*=\s*["\'])[^"\']+([ "\'])',
            f'\\g<1>{new_version}\\g<2>',
            content
        )
        init_file.write_text(content)
        print(f"✓ Updated {init_file}")
    
    # Update VERSION file
    version_file = root / "VERSION"
    version_file.write_text(f"{new_version}\n")
    print(f"✓ Updated {version_file}")
    
    # Update CHANGELOG.md (add new version section placeholder)
    changelog_file = root / "CHANGELOG.md"
    if changelog_file.exists():
        content = changelog_file.read_text()
        if f"## [{new_version}]" not in content:
            # Add new version section after the header
            header_end = content.find("\n", content.find("# Changelog"))
            new_section = f"\n\n## [{new_version}] - {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}\n\n### Added\n\n### Changed\n\n### Deprecated\n\n### Removed\n\n### Fixed\n\n### Security\n"
            content = content[:header_end] + new_section + content[header_end:]
            changelog_file.write_text(content)
            print(f"✓ Updated {changelog_file}")


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    
    bump_type = sys.argv[1].lower()
    if bump_type not in ["major", "minor", "patch"]:
        print(f"Error: Invalid bump type '{bump_type}'")
        print("Use: major, minor, or patch")
        sys.exit(1)
    
    current_version = get_current_version()
    new_version = bump_version(current_version, bump_type)
    
    print(f"Current version: {current_version}")
    print(f"New version: {new_version}")
    print()
    
    confirm = input("Proceed with version bump? [y/N]: ")
    if confirm.lower() != 'y':
        print("Cancelled")
        sys.exit(0)
    
    update_version_files(new_version)
    
    print()
    print("Next steps:")
    print(f"  1. git add -A")
    print(f"  2. git commit -m 'chore: bump version to {new_version}'")
    print(f"  3. git tag v{new_version}")
    print(f"  4. git push && git push --tags")
    print()
    print("This will trigger the release workflow!")


if __name__ == "__main__":
    main()
