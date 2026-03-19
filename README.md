# Sandbox Manager

A web-based interface for managing LXD virtual machines and containers. Designed for classrooms and workshops where you need to quickly create identical VMs for participants and clean them up afterwards.

## Features

- **Bulk VM Creation** - Create multiple VMs at once with pre-flight resource checks
- **One-Click Operations** - Start, stop, or delete all VMs in bulk
- **SSH ProxyJump** - Secure SSH access with auto-generated jump user and SSH configs
- **Resource Monitoring** - Real-time CPU, RAM, and disk usage
- **Workshop Ready** - Perfect for training environments with temporary VM needs

## Requirements

- Linux host with LXD installed and configured
- Python 3.10+
- 50GB+ free disk space (depending on VM count)

## Installation

```bash
# Clone repository
git clone https://github.com/semanticlib/sandbox.git
cd sandbox

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Pre-setup

Create at least one VM in LXD using either CLI or LXD Web UI. For example:

```bash
lxc launch ubuntu:24.04 test-vm --vm
```

This step will download the ubuntu:24.04 image. The Sandbox app will only show these downloaded images in the settings page.

## Running

### Development

```bash
source .venv/bin/activate
python main.py
# Access at http://localhost:8000
```

### Production (Systemd + Caddy Reverse Proxy)

1. **Configure environment:**
   ```bash
   sudo cp env.example /etc/sandbox/.env
   sudo nano /etc/sandbox/.env  # Set SECRET_KEY and HOST_SERVER_IP at minimum
   ```

2. **Install systemd service:**
   ```bash
   sudo cp sandbox.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable sandbox
   sudo systemctl start sandbox
   ```

3. **Setup Caddy reverse proxy (automatic HTTPS):**
   ```bash
   # Install Caddy: https://caddyserver.com/docs/install
   sudo cp Caddyfile /etc/caddy/Caddyfile
   sudo nano /etc/caddy/Caddyfile  # Change sandbox.example.com to your domain
   sudo systemctl reload caddy
   ```

4. **Check status:**
   ```bash
   sudo systemctl status sandbox
   sudo systemctl status caddy
   # Access at: https://your-domain.com
   ```

## First Setup

1. Open the web interface
2. Create admin account on first launch
3. Configure LXD connection in Settings (socket or HTTPS)
4. Set default VM resources (CPU, RAM, disk, cloud-init template)
5. Create VMs individually or in bulk

## Testing

```bash
source .venv/bin/activate
./scripts/test.sh          # Run all tests
./scripts/test.sh fast     # Fast mode (no coverage)
./scripts/test.sh html     # Generate coverage report
```

## Security Notes

- Always set a strong `SECRET_KEY` in production
- Use Caddy reverse proxy for automatic HTTPS (ports 80/443 must be open)
- **Important:** Auth cookies require HTTPS (`secure=True` flag). The app will work over HTTP for local testing, but login sessions won't persist without HTTPS.
