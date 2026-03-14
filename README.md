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
git clone <repository-url>
cd sandbox

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate secure secret key
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env
```

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
   sudo nano /etc/sandbox/.env  # Set SECRET_KEY and other values
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

## Bulk Operations

- **Bulk Create** - Enter VM names (one per line), click "Check Prerequisites", then "Start Bulk Create"
- **Start/Stop All** - Use toolbar buttons to manage all VMs at once
- **Delete All** - Clean up all VMs after workshop ends

## API Endpoints

- `GET /health` - Health check with LXD status and disk space
- `POST /instances/bulk/create` - Create multiple VMs
- `POST /instances/bulk/start` - Start multiple VMs
- `POST /instances/bulk/stop` - Stop multiple VMs
- `POST /instances/bulk/delete` - Delete multiple VMs

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
- Rate limiting protects against brute-force login attempts
- Input validation prevents path traversal and injection attacks
- Password requirements: 8+ chars, uppercase, lowercase, number, special char
