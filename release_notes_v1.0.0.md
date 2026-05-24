# Release Notes: API v1.0.0 - Premium Telegram FastAPI Console & SPA Dashboard

We are thrilled to announce the official **v1.0.0** release of the **Telegram FastAPI Integration** project! 

This release graduates the application from a simple backend integration into a state-of-the-art **Telegram Command Center & Console**. It ships with a fully responsive, dark-themed Single Page Application (SPA) dashboard served right from the root directory (`/`), a highly robust MTProto auth system, rich messaging, local media uploads, group administration controls, and complete Python 3.13 compatibility patches.

---

### 🚀 What's New in v1.0.0

#### 1. Premium SPA Console Dashboard (`web/index.html`)
* **Cyberpunk Aesthetics**: Designed using deep space cybersecurity dark gradients, futuristic glassmorphic overlays (`backdrop-filter`), smooth hover transitions, and fluid animations.
* **Direct Token Sign-In**: Added an alternative authentication tab. If you already have a JWT, you can paste it and log in instantly; a client-side parser decodes the JWT payload to restore your active account phone and credentials.
* **Universal Mobile Viewport Support**: Complete responsive layout re-design. Sidebar navigation collapses into a sliding hamburger menu drawer, and the chats dual-pane workspace uses slide-in absolute panels with custom back-navigation overlays on mobile and tablet screens.
* **Direct Swagger Docs Integration**: Integrated direct navigation links to Swagger UI (`/docs`) in both the landing screen hero and the dashboard sidebar footer.

#### 2. Core API Endpoint Additions (`main.py`)
* **`POST /chats/invite`**: Invite or add participants to groups/supergroups/channels by username, phone number, or numeric ID.
* **`POST /chats/remove-user`**: Remove/kick participants from any group or channel using Telegram's high-level `kick_participant` handlers.
* **`GET /chats/list-own`**: Lists only public or private groups and channels created and owned by the logged-in user.
* **`POST /renew-token`**: Regenerates a fresh, stateless JWT access token on-demand and securely delivers it directly to your Telegram **Saved Messages** ("me") chat.

#### 3. Performance & Safety Safeguards
* **Flood Wait Elimination**: Replaced unlimited historical message fetches (`limit=None`) with a safe default cap of **35 messages**. This dramatically speeds up chat history rendering while completely protecting your account against Telegram MTProto rate-limit blocks.

#### 4. Compatibility & VPS Production Support
* **Python 3.13 Compatibility**: Added a dynamic `imghdr` polyfill inside `telegram_client.py` to prevent import errors caused by Python 3.13's deprecation of the standard `imghdr` module.
* **Automated VPS Deployer**: Includes a custom bash script (`setup.sh`) that automates isolated virtual environment setups, pip dependencies installation, and registers a persistent background `systemd` daemon `telegram-api.service` to start on boot.

---

### 🔌 REST API Coverage

* **Telegram Auth**:
  * `POST /login` - Request OTP code.
  * `POST /verify` - Verify code (OTP & 2FA) and issue stateless JWT token.
  * `GET /telegram/status` - Live authorization check.
  * `POST /logout` - Invalidate credentials and terminate Telethon sessions.
  * `POST /renew-token` - Renew JWT and deliver it to Saved Messages.
* **Telegram User Profile**:
  * `GET /me` - Account profile card.
  * `GET /list-contacts` - Addresses book list (includes DC ID, bot, and mutual metadata).
* **Dialogs & Messaging**:
  * `GET /list-chats` - List all active dialogues, groups, and channels.
  * `GET /chats/list-own` - List owned groups/channels.
  * `POST /chats/message/send` - Dispatches Markdown text messages.
  * `POST /chats/message/send-file` - Dispatches local documents with captions.
  * `POST /chats/message/delete` - One-click message removal.
  * `POST /chats/invite` - Invite member to chat.
  * `POST /chats/remove-user` - Kick member from chat.
  * `GET /chats/list-messages/{chat_type}` - Pulls chat history (Text, Media, or All).
  * `POST /chats/list-message/by-date` - Backups chat history by date range.

---

### 🛠️ Getting Started

```bash
# 1. Navigate to directory
cd telegram-api

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install packages
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure .env file manually
nano .env

# 5. Launch
uvicorn main:app --reload --port 9000
```
Open `http://localhost:9000/` in your browser to run the console or `http://localhost:9000/docs` to explore Swagger!
