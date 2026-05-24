how to use the setup.sh script I gave you:

1️⃣ Upload/Place the script on your VPS

Suppose your VPS home directory is /home/ubuntu

Save the script as setup.sh in /home/ubuntu/telegram-api/

mkdir -p ~/telegram-api
cd ~/telegram-api
nano setup.sh   # Paste the script and save

2️⃣ Make the script executable
chmod +x setup.sh

3️⃣ Create your .env manually

Before running the script, create a .env file in the same directory:

nano ~/telegram-api/.env


Add your Telegram API credentials and secret key:

API_ID=20295426
API_HASH=508dea8a3dcdc08291fg71cd30e4bebehh
SECRET_KEY=your-very-secure-secret-key


Save and exit.

⚠️ Make sure there’s no trailing spaces or quotes.

4️⃣ Run the setup script
cd ~/telegram-api
./setup.sh


This will:

Create a virtual environment

Install all dependencies

Start the FastAPI app temporarily using uvicorn

Create a systemd service for production

Enable and start the service automatically

5️⃣ Check if it’s running
sudo systemctl status telegram-api


To follow logs in real-time:

journalctl -u telegram-api -f


The API should now be accessible at http://<your_vps_ip>:9000/

6️⃣ Optional: Stop/Restart
sudo systemctl stop telegram-api
sudo systemctl start telegram-api
sudo systemctl restart telegram-api


💡 Tip: If you ever update your Python code, you can just restart the service to apply changes.