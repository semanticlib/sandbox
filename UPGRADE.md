# Upgrade Guide

This document describes how to upgrade Sandbox Manager from one version to another.

## General Upgrade Process

```bash
# 1. Backup your data
sudo systemctl stop sandbox
cp -r /opt/sandbox /opt/sandbox.backup
cp -r /etc/sandbox /etc/sandbox.backup

# 2. Pull latest changes
cd /opt/sandbox
git pull

# 3. Install updated dependencies
source .venv/bin/activate
pip install -r requirements.txt

# 4. Run database migrations (if any)
# Check UPGRADE.md for version-specific migration steps

# 5. Restart service
sudo systemctl restart sandbox
sudo systemctl status sandbox
```

## Version-Specific Notes

### v0.2.0 (Upcoming)

**Breaking Changes:** None

**New Features:**
- Pattern-based bulk VM creation

**Migration Steps:**
1. No database changes
2. No configuration changes
3. Simply update and restart

### v0.1.0 (Initial Release)

**Initial installation:**
```bash
git clone https://github.com/semanticlib/sandbox.git
cd sandbox
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Rolling Back

If you encounter issues:

```bash
# Stop service
sudo systemctl stop sandbox

# Restore backup
rm -rf /opt/sandbox
cp -r /opt/sandbox.backup /opt/sandbox
cp -r /etc/sandbox.backup /etc/sandbox

# Restart
sudo systemctl start sandbox
```

## Database Migrations

Currently, the application uses SQLAlchemy's `create_all()` which auto-creates tables.
Future versions may use Alembic for migrations.

Check the release notes for any manual migration steps.

## Reporting Issues

If you encounter problems during upgrade:

1. Check the [Issues](https://github.com/YOUR_USERNAME/sandbox/issues) page
2. Review logs: `sudo journalctl -u sandbox -f`
3. Open a new issue with:
   - Previous version
   - Target version
   - Error messages
   - Steps to reproduce
