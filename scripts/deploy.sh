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

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "  1. Edit $ENV_DIR/.env to configure settings"
echo "  2. Start service: sudo systemctl start $APP_NAME"
echo "  3. Check status: sudo systemctl status $APP_NAME"
echo "  4. Access at: http://localhost:8000"
