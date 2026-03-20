#!/bin/bash
# Production deployment script for Sandbox Manager
# Usage: sudo ./scripts/deploy.sh

set -e

APP_NAME="sandbox"
APP_USER="sandbox"
APP_DIR="/opt/$APP_NAME"
ENV_DIR="/etc/$APP_NAME"

echo "🚀 Deploying Sandbox Manager..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo ./scripts/deploy.sh)"
    exit 1
fi

# Create app user
if ! id -u "$APP_USER" &>/dev/null; then
    echo "Creating user: $APP_USER"
    useradd --system --no-create-home --shell /bin/false "$APP_USER"
fi

# Create directories
echo "Creating directories..."
mkdir -p "$APP_DIR"
mkdir -p "$ENV_DIR"
mkdir -p "$APP_DIR/_instances"
mkdir -p "$APP_DIR/static"

# Copy application files
echo "Copying application files..."
cp -r ./* "$APP_DIR/"

# Set ownership
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$ENV_DIR"

# Copy environment file
if [ ! -f "$ENV_DIR/.env" ]; then
    echo "Creating environment file..."
    cp env.example "$ENV_DIR/.env"

    # Generate SECRET_KEY
    SECRET_KEY=$(openssl rand -hex 32)
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_DIR/.env"

    # Set default HOST to localhost (secure by default)
    sed -i "s/^HOST=.*/HOST=127.0.0.1/" "$ENV_DIR/.env"

    # Ask user about port configuration
    echo ""
    echo "📡 Network Configuration:"
    echo ""
    read -p "Use default port 8000? [Y/n]: " use_default_port
    if [[ ! "$use_default_port" =~ ^[Nn]$ ]]; then
        echo "✓ Using default port 8000"
    else
        read -p "Enter custom port [8000]: " custom_port
        if [ -z "$custom_port" ]; then
            custom_port="8000"
        fi
        # Validate port number
        if [[ "$custom_port" =~ ^[0-9]+$ ]] && [ "$custom_port" -ge 1 ] && [ "$custom_port" -le 65535 ]; then
            sed -i "s/^PORT=.*/PORT=$custom_port/" "$ENV_DIR/.env"
            echo "✓ Port set to $custom_port"
        else
            echo "⚠ Invalid port number. Using default port 8000"
        fi
    fi

    # Auto-detect public IP for SSH config
    echo ""
    echo "🌐 Detecting public IP..."
    DETECTED_IP=$(curl -s --max-time 5 https://ifconfig.me 2>/dev/null || echo "")

    if [ -n "$DETECTED_IP" ]; then
        echo "✓ Detected public IP: $DETECTED_IP"
        read -p "Use this IP for SSH config? [Y/n]: " use_detected_ip
        if [[ ! "$use_detected_ip" =~ ^[Nn]$ ]]; then
            HOST_IP="$DETECTED_IP"
            echo "✓ Using detected IP: $HOST_IP"
        else
            read -p "Enter custom IP for SSH config: " custom_ip
            if [ -n "$custom_ip" ]; then
                HOST_IP="$custom_ip"
                echo "✓ Using custom IP: $HOST_IP"
            else
                HOST_IP="$DETECTED_IP"
                echo "✓ Using detected IP: $HOST_IP"
            fi
        fi
    else
        echo "⚠ Could not detect public IP (no internet or timeout)"
        read -p "Enter LXD host server IP for SSH config [10.10.1.1]: " host_ip_input
        if [ -z "$host_ip_input" ]; then
            HOST_IP="10.10.1.1"
        else
            HOST_IP="$host_ip_input"
        fi
        echo "✓ LXD host IP set to $HOST_IP"
    fi

    sed -i "s/^HOST_SERVER_IP=.*/HOST_SERVER_IP=$HOST_IP/" "$ENV_DIR/.env"

    # Set permissions
    chown "$APP_USER:$APP_USER" "$ENV_DIR/.env"
    chmod 600 "$ENV_DIR/.env"
fi

# Create virtual environment
echo "Setting up Python environment..."
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Install systemd service
echo "Installing systemd service..."
cp sandbox.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable $APP_NAME

# Get configured port for display
CONFIGURED_PORT=$(grep "^PORT=" "$ENV_DIR/.env" | cut -d'=' -f2)
if [ -z "$CONFIGURED_PORT" ]; then
    CONFIGURED_PORT="8000"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Configuration:"
echo "  - Port: $CONFIGURED_PORT"
echo "  - Environment: $ENV_DIR/.env"
echo ""
echo "Next steps:"
echo "  1. Start service: sudo systemctl start $APP_NAME"
echo "  2. Check status: sudo systemctl status $APP_NAME"
echo "  3. Access at: http://localhost:$CONFIGURED_PORT"
