# Sandbox Manager

A web-based interface for managing LXD virtual machines and containers. Designed for classrooms and workshops where you need to quickly create identical VMs for participants and clean them up afterwards.

![Dashboard](screenshots/dashboard.png)

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

## Pre-setup

Create at least one VM in LXD using either CLI or LXD Web UI. For example:

```bash
lxc launch ubuntu:24.04 test-vm --vm
```

This step will download the `ubuntu:24.04` image. The Sandbox app will only show these downloaded images in the settings page.

## Installation

```bash
git clone https://github.com/semanticlib/sandbox.git
cd sandbox
sudo ./scripts/deploy.sh
sudo systemctl status sandbox
```

**Secure Access using SSH Tunnel**

Use SSH Tunneling to access the app

```bash
ssh -L 8000:localhost:8000 user@<host-ip>
```

Open `http://localhost:8000` in your browser

**Custom Port:**

To use a different port, set `PORT` in `/etc/sandbox/.env`:
```bash
PORT=9000
```

Then restart the service:
```bash
sudo systemctl restart sandbox
```

> [!IMPORTANT]
> Auth cookies require HTTPS (`secure=True` flag). The login sessions won't persist without HTTPS.
> Point any FQDN to your server and use Caddy for automatic SSL for your domain. See example [Caddyfile](Caddyfile) for reference.

## SSH Access & Network Architecture

### Connection Method: SSH ProxyJump

The Sandbox Manager uses **SSH ProxyJump** to provide secure access to guest VMs without requiring direct network exposure or shell access to the LXD host.

![User Flow Diagram](screenshots/user-flow-diagram.svg)

**How it works:**

1. The SSH connection jumps through the host machine to reach the guest VM
2. Auto-generated SSH configs with `launch-server.bat` script are provided for each VM

### Per-VM configuration with unique SSH key pairs (Ed25519)

For enhanced security, the Sandbox Manager **automatically generates unique SSH key pairs** for each VM user.

**What you get:**

1. **Private key download** - Download the Ed25519 private key from the web interface
2. **SSH config template** - Pre-configured SSH config with all connection details
3. **Launch Server** - Launch server using `launch-server.bat` script

Users can directly connect to the VM by running `launch-server.bat` on Windows.

On Linux, same script can be run from the terminal:
```bash
cd /path/to/downloaded-folder
sh launch-server.bat
```

### No Shell Access on LXD Host

**Important:** Users **do not have shell access** to the LXD host machine. This is by design:

- Users can only access the guest VMs they're authorized to use
- The LXD host remains isolated and secure
- All VM management is done through the web interface
- SSH access is limited to guest VMs only (via ProxyJump)

This model is ideal for:
- **Classroom environments** - Students get VM access without host access
- **Workshop setups** - Participants can't interfere with host configuration
- **Multi-tenant systems** - Clean separation between host and guest access

### LocalForward: Accessing Applications in Guest VMs

To access web applications or services running inside guest VMs, the SSH connection includes **LocalForward** (local port forwarding).

**How LocalForward works:**

Add `LocalForward` rules in the SSH Config template for each participant in the template (_Settings > Connection Templates_). E.g.,

```config
LocalForward 8080 localhost:80
LocalForward 3000 localhost:3000
```

**After connecting to SSH:**
- Open your browser and navigate to `http://localhost:8080`
- Traffic is securely tunneled through SSH to the VM's port 80
- No need to expose VM ports to the external network

**Common use cases:**
| Service | Local Forward | VM Port | Access URL |
|---------|---------|---------------|------------|
| Web server default | 8080 | 80 | http://localhost:8080 |
| Custom web app | 3000 | 3000 | http://localhost:3000 |


## Why This is a Secure Model

The Sandbox Manager architecture follows **defense in depth** principles:

**Security benefits:**

| Principle | Implementation |
|-----------|----------------|
| **Minimal Privilege** | Users only access their assigned VMs, not the host |
| **Network Isolation** | VMs don't need public IPs or exposed ports |
| **Encrypted Traffic** | All SSH traffic (including LocalForward) is encrypted |
| **No Direct Access** | Host firewall can block direct VM access |
| **Audit Trail** | SSH connections are logged and traceable |
| **Ephemeral Access** | SSH configs can be regenerated/revoked anytime |

**Attack surface comparison:**

| Approach | Host Access | VM Access | Network Exposure |
|----------|-------------|-----------|------------------|
| **Direct VM SSH** | ❌ Not needed | ✅ Direct | ⚠️ VMs need public IPs |
| **Bastion Host** | ⚠️ Bastion accessible | ✅ Via bastion | ⚠️ Bastion exposed |
| **ProxyJump (Sandbox)** | ✅ Isolated | ✅ Via jump | ✅ No VM exposure |

**Key security features:**

1. **Host isolation** - LXD host SSH is separate from VM access
2. **No port forwarding abuse** - LocalForward only forwards to localhost on VM
3. **Credential separation** - VM credentials independent from host credentials
4. **No persistent tunnels** - Connections close when SSH session ends


## Development

Read the [Contribution Guidelines](CONTRIBUTING.md) for more information on development setup, testing and submitting pull requests.
