#!/bin/bash

# =========================
# Telegram API Setup Script
# =========================

# Config
PROJECT_DIR="$HOME/telegram-api"
VENV_DIR="$PROJECT_DIR/venv"
IP_ADDRESS="0.0.0.0"
PORT="9000"
SYSTEMD_SERVICE="/etc/systemd/system/telegram-api.service"

# Create project directory
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR || exit

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv $VENV_DIR

# Activate virtual environment
source $VENV_DIR/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install fastapi==0.95.2 \
            uvicorn==0.22.0 \
            python-dotenv==1.0.0 \
            telethon==1.28.5 \
            PyJWT==2.7.0 \
            python-multipart==0.0.6

# Inform user to create .env manually
echo "⚠️  Please create your .env file manually in $PROJECT_DIR"
echo "Example .env:"
echo "API_ID=YOUR_API_ID"
echo "API_HASH=YOUR_API_HASH"
echo "SECRET_KEY=your-very-secure-secret-key"

# Run the app (temporary)
echo "Starting FastAPI app on $IP_ADDRESS:$PORT..."
nohup $VENV_DIR/bin/uvicorn main:app --host $IP_ADDRESS --port $PORT --reload > telegram-api.log 2>&1 &

# Create systemd service for production
echo "Creating systemd service..."
sudo bash -c "cat > $SYSTEMD_SERVICE" <<EOL
[Unit]
Description=Telegram API FastAPI Service
After=network.target

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/uvicorn main:app --host $IP_ADDRESS --port $PORT
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable telegram-api
sudo systemctl start telegram-api

echo "✅ Setup complete!"
echo "Check status: sudo systemctl status telegram-api"
echo "Logs: journalctl -u telegram-api -f"
