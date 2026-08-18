import os
import asyncio
import sys
import types

# Python 3.13+ compatibility patch for Telethon
if "imghdr" not in sys.modules:
    imghdr_mock = types.ModuleType("imghdr")
    imghdr_mock.what = lambda file, h=None: None
    sys.modules["imghdr"] = imghdr_mock

from telethon import TelegramClient
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.contacts import GetContactsRequest
from typing import Optional, Dict, Any
from datetime import datetime, date, timezone
import logging
from auth import create_token



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_ID = int(os.getenv("API_ID", 20295429))
API_HASH = os.getenv("API_HASH", "508dea8a3dcdc08291f71cd30e4bebe1")
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Global dictionary for per-phone locks
_client_locks = {}

def get_lock(phone: str):
    """Return a per-phone asyncio.Lock to prevent concurrent SQLite writes"""
    if phone not in _client_locks:
        _client_locks[phone] = asyncio.Lock()
    return _client_locks[phone]

_clients = {}  # Cache for clients

def get_client(phone: str) -> TelegramClient:
    """Get or create a cached Telegram client instance to prevent SQLite locks"""
    if phone not in _clients or _clients[phone] is None:
        _clients[phone] = TelegramClient(
            f"{SESSIONS_DIR}/{phone}",
            API_ID,
            API_HASH,
            connection_retries=3,
            sequential_updates=True
        )
    return _clients[phone]

# ------------------- Telegram Operations -------------------

async def login(phone: str) -> Dict[str, Any]:
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.connect()
        try:
            if not await client.is_user_authorized():
                result = await client.send_code_request(phone)
                return {"phone_code_hash": result.phone_code_hash}
            return {"phone_code_hash": None, "message": "Already authorized"}
        except Exception as e:
            logger.error(f"Login failed for {phone}: {str(e)}")
            raise
        finally:
            await client.disconnect()

async def verify_code(phone: str, code: str, password: Optional[str] = None, phone_code_hash: str = "") -> Dict[str, Any]:
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.connect()
        try:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    raise Exception("Password is required due to 2FA being enabled.")
                await client.sign_in(password=password)

            token_payload = {
                "phone": phone,
                "created_at": datetime.utcnow().isoformat()
            }
            token = create_token(token_payload)

            message = (
                f"🔐 *Persistent API Token* 🔐\n\n"
                f"This token will work until:\n"
                f"1. You log out of Telegram\n"
                f"2. Delete this session\n\n"
                f"Token: `{token}`\n"
                f"Account: {phone}\n\n"
                f"⚠️ Keep this secure - it won't expire automatically"
            )

            await client.send_message("me", message, parse_mode='markdown')

            return {
                "access_token": token,
                "persistent": True,
                "message": "Token saved to Telegram saved messages"
            }
        except Exception as e:
            logger.error(f"Verification failed for {phone}: {str(e)}")
            raise
        finally:
            await client.disconnect()

async def logout(phone):
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.connect()
        try:
            await client.log_out()
            session_file = f"{SESSIONS_DIR}/{phone}.session"
            if os.path.exists(session_file):
                os.remove(session_file)
        except Exception as e:
            logger.error(f"Logout failed for {phone}: {str(e)}")
        finally:
            await client.disconnect()

async def get_me(phone):
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        me = await client.get_me()
        user_dict = {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone,
            "is_bot": me.bot,
            "verified": me.verified,
            "restricted": me.restricted,
            "status": str(me.status),
            "dc_id": me.photo.dc_id if me.photo else None
        }
        await client.disconnect()
        return {"user": user_dict}

async def get_contacts(phone):
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        try:
            result = await client(GetContactsRequest(hash=0))
            contacts = result.contacts

            serialized_contacts = []
            for contact in contacts:
                user = next((u for u in result.users if u.id == contact.user_id), None)
                if user:
                    contact_dict = {
                        "id": user.id,
                        "first_name": getattr(user, 'first_name', ''),
                        "last_name": getattr(user, 'last_name', ''),
                        "username": getattr(user, 'username', ''),
                        "phone": getattr(user, 'phone', ''),
                        "mutual_contact": getattr(contact, 'mutual', False),
                        "is_user": True,
                        "is_bot": getattr(user, 'bot', False),
                        "status": str(getattr(user, 'status', 'unknown')),
                        "photo": {
                            "has_photo": bool(getattr(user, 'photo', None)),
                            "dc_id": getattr(getattr(user, 'photo', None), 'dc_id', None)
                        } if hasattr(user, 'photo') else None
                    }
                    serialized_contacts.append(contact_dict)

            return serialized_contacts
        finally:
            await client.disconnect()

async def get_dialogs(phone):
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        dialogs = await client.get_dialogs()
        await client.disconnect()
        return [
            {
                "id": d.id,
                "name": d.name,
                "title": d.title,
                "is_user": d.is_user,
                "is_group": d.is_group,
                "is_channel": d.is_channel,
                "is_bot": getattr(d.entity, 'bot', False)
            }
            for d in dialogs
        ]

async def send_message(phone, chat_id, message, reply_to=None):
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        entity = await client.get_entity(int(chat_id))
        msg = await client.send_message(entity, message, reply_to=reply_to)
        await client.disconnect()
        return {
            "success": True,
            "message_id": msg.id,
            "chat_id": int(chat_id),
            "date": msg.date.isoformat() if msg.date else None
        }
async def send_file_message(phone: str, chat_id: int, file_path: str, caption: str = None, reply_to: int = None):
    """
    Send a file (image, video, document, etc.) to a chat with optional caption and thread/topic ID.
    """
    client = get_client(phone)
    lock = get_lock(phone)

    async with lock:
        await client.start()
        entity = await client.get_entity(int(chat_id))  # Resolve chat entity
        msg = await client.send_file(entity, file=file_path, caption=caption, reply_to=reply_to)
        await client.disconnect()

        return {
            "success": True,
            "message_id": msg.id,
            "chat_id": int(chat_id),
            "date": msg.date.isoformat() if msg.date else None
        }

async def delete_message(phone, chat_id, message_id):
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        result = await client.delete_messages(int(chat_id), message_id)
        await client.disconnect()
        return {"success": True, "deleted": result}

async def list_all_messages(phone, chat_id, limit=35):
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        messages = []
        async for message in client.iter_messages(int(chat_id), limit=limit):
            try:
                messages.append({
                    "id": message.id,
                    "date": str(message.date),
                    "text": message.text,
                    "sender_id": getattr(message.sender, 'id', None),
                    "sender_name": (getattr(message.sender, 'first_name', '') or '') + " " + (getattr(message.sender, 'last_name', '') or ''),
                    "media": bool(message.media),
                    "reply_to": message.reply_to.reply_to_msg_id if message.reply_to else None
                })
            except Exception as e:
                logger.error(f"Error serializing message {message.id}: {str(e)}")
                continue
        await client.disconnect()
        return messages

def parse_dt(d, is_end_of_day: bool = False) -> Optional[datetime]:
    """Parse flexible date input (datetime, date, str) into UTC timezone-aware datetime."""
    if not d:
        return None
    if isinstance(d, datetime):
        if d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d
    if isinstance(d, date):
        if is_end_of_day:
            return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    if isinstance(d, str):
        d_str = d.strip()
        if not d_str:
            return None
        if len(d_str) == 10 and d_str[4] == '-' and d_str[7] == '-':
            try:
                parsed_d = datetime.strptime(d_str, "%Y-%m-%d")
                if is_end_of_day:
                    return datetime(parsed_d.year, parsed_d.month, parsed_d.day, 23, 59, 59, tzinfo=timezone.utc)
                return datetime(parsed_d.year, parsed_d.month, parsed_d.day, 0, 0, 0, tzinfo=timezone.utc)
            except ValueError:
                pass
        try:
            parsed = datetime.fromisoformat(d_str.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None
    return None

async def fetch_messages_by_date(phone: str, chat_id: int, date_from=None, date_to=None, topic_id=None):
    """
    Fetch messages from a chat within a specific date range using a per-phone lock
    to avoid SQLite database lock issues in Telethon sessions.
    Supports optional topic_id to filter by specific forum topic.
    """
    lock = get_lock(phone)  # make sure get_lock(phone) returns an asyncio.Lock()
    
    dt_from = parse_dt(date_from, is_end_of_day=False)
    dt_to = parse_dt(date_to, is_end_of_day=True)

    async with lock:
        client = get_client(phone)
        await client.start()
        messages = []
        max_fetch = 500 if not dt_from else 2000
        reply_to_arg = int(topic_id) if topic_id is not None and str(topic_id).strip() != "" else None
        try:
            async for msg in client.iter_messages(int(chat_id), offset_date=dt_to, limit=max_fetch, reply_to=reply_to_arg):
                if msg.date:
                    msg_date = msg.date
                    if msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)
                    if dt_to and msg_date > dt_to:
                        continue
                    if dt_from and msg_date < dt_from:
                        break

                sender_name = ""
                if msg.sender:
                    first_name = getattr(msg.sender, "first_name", "") or ""
                    last_name = getattr(msg.sender, "last_name", "") or ""
                    title = getattr(msg.sender, "title", "") or ""
                    sender_name = f"{first_name} {last_name}".strip() or title

                msg_topic_id = None
                reply_to_id = None
                if msg.reply_to:
                    reply_to_id = getattr(msg.reply_to, 'reply_to_msg_id', None)
                    msg_topic_id = getattr(msg.reply_to, 'reply_to_top_id', None) or reply_to_id

                messages.append({
                    "id": msg.id,
                    "date": str(msg.date),
                    "text": msg.text,
                    "sender_id": getattr(msg.sender, "id", None),
                    "sender_name": sender_name,
                    "media": bool(msg.media),
                    "reply_to": reply_to_id,
                    "topic_id": msg_topic_id
                })
        finally:
            await client.disconnect()

        return messages

async def is_session_active(phone: str) -> bool:
    """Check if session file exists and client is authorized."""
    session_file = f"{SESSIONS_DIR}/{phone}.session"
    if not os.path.exists(session_file):
        return False
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        try:
            await client.connect()
            authorized = await client.is_user_authorized()
            return authorized
        except Exception as e:
            logger.error(f"Session active check failed for {phone}: {str(e)}")
            return False
        finally:
            await client.disconnect()

async def fetch_messages(phone: str, chat_id: int, date_from=None, date_to=None, topic_id=None):
    """Alias for fetch_messages_by_date to support main.py calls"""
    return await fetch_messages_by_date(phone, chat_id, date_from, date_to, topic_id)

async def invite_to_group(phone: str, chat_id: int, user_id: str):
    """
    Invite a user (by username, phone, or numeric ID) to a group or channel.
    """
    from telethon.tl.functions.channels import InviteToChannelRequest
    from telethon.tl.functions.messages import AddChatUserRequest
    from telethon.tl.types import Channel
    
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        try:
            # Resolve entities
            chat_entity = await client.get_entity(int(chat_id))
            
            # Resolve user_entity. If it is an ID, parse it as integer
            try:
                user_val = int(user_id)
            except ValueError:
                user_val = user_id
            
            user_entity = await client.get_entity(user_val)
            
            if isinstance(chat_entity, Channel):
                # Megagroups and Channels
                result = await client(InviteToChannelRequest(
                    channel=chat_entity,
                    users=[user_entity]
                ))
            else:
                # Basic standard groups
                result = await client(AddChatUserRequest(
                    chat_id=chat_entity.id,
                    user_id=user_entity,
                    fwd_limit=0
                ))
            
            return {
                "success": True,
                "message": f"Successfully invited user '{user_id}' to group/channel '{chat_id}'"
            }
        except Exception as e:
            logger.error(f"Invite to group/channel failed for {phone}: {str(e)}")
            raise e
        finally:
            await client.disconnect()

async def get_own_groups(phone: str):
    """
    Get a list of groups and channels created/owned by the user.
    """
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        try:
            dialogs = await client.get_dialogs()
            own_chats = []
            for d in dialogs:
                if (d.is_group or d.is_channel) and getattr(d.entity, 'creator', False):
                    is_megagroup = getattr(d.entity, 'megagroup', False)
                    is_broadcast = d.is_channel and not is_megagroup
                    own_chats.append({
                        "id": d.id,
                        "name": d.name,
                        "title": d.title,
                        "type": "supergroup" if is_megagroup else ("channel" if is_broadcast else "group"),
                        "username": getattr(d.entity, 'username', None)
                    })
            return own_chats
        except Exception as e:
            logger.error(f"Get own groups failed for {phone}: {str(e)}")
            raise e
        finally:
            await client.disconnect()

async def get_report_summary(phone: str):
    """
    Generate an aggregated telemetry audit report for the account.
    """
    from telethon.tl import functions
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        try:
            # 1. Fetch dialogues and contacts in a single unified session
            dialogs = await client.get_dialogs()
            raw_contacts = await client(functions.contacts.GetContactsRequest(hash=0))
            
            # Serialize contacts
            contacts = []
            if raw_contacts and hasattr(raw_contacts, 'users'):
                contacts = raw_contacts.users

            # 2. Contacts Audit Breakdown
            total_contacts = len(contacts)
            mutual_count = 0
            bot_count = 0
            friends_count = 0
            
            for u in contacts:
                is_bot = getattr(u, 'bot', False)
                is_mutual = getattr(u, 'mutual', False)
                if is_bot:
                    bot_count += 1
                elif is_mutual:
                    mutual_count += 1
                else:
                    friends_count += 1

            # 3. Dialogues & Chats Audit Breakdown
            total_chats = len(dialogs)
            groups_count = 0
            channels_count = 0
            dialogue_bots_count = 0
            
            # 4. Ownership Breakdown
            own_groups = 0
            own_channels = 0
            
            for d in dialogs:
                is_group = d.is_group
                is_channel = d.is_channel
                is_bot = getattr(d.entity, 'bot', False)
                is_creator = getattr(d.entity, 'creator', False)
                
                # dialogue type counts
                if is_bot:
                    dialogue_bots_count += 1
                if is_group:
                    groups_count += 1
                if is_channel:
                    channels_count += 1
                
                # ownership counts
                if is_creator:
                    is_megagroup = getattr(d.entity, 'megagroup', False)
                    is_broadcast = is_channel and not is_megagroup
                    if is_megagroup or is_group:
                        own_groups += 1
                    elif is_broadcast:
                        own_channels += 1

            return {
                "contacts": {
                    "friends": friends_count,
                    "mutual": mutual_count,
                    "none": bot_count,
                    "all": total_contacts
                },
                "chats": {
                    "total": total_chats,
                    "groups": groups_count,
                    "channels": channels_count,
                    "bots": dialogue_bots_count
                },
                "ownership": {
                    "own_groups": own_groups,
                    "own_channels": own_channels,
                    "own_bots": dialogue_bots_count or bot_count or 0
                }
            }
        except Exception as e:
            logger.error(f"Get report summary failed for {phone}: {str(e)}")
            raise e
        finally:
            await client.disconnect()

async def remove_from_group(phone: str, chat_id: int, user_id: str):
    """
    Remove/kick a user from a group or channel.
    """
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        try:
            # Resolve entities
            chat_entity = await client.get_entity(int(chat_id))
            
            # Resolve user_entity
            try:
                user_val = int(user_id)
            except ValueError:
                user_val = user_id
                
            user_entity = await client.get_entity(user_val)
            
            # Kick user
            await client.kick_participant(chat_entity, user_entity)
            
            return {
                "success": True,
                "message": f"Successfully removed user '{user_id}' from group/channel '{chat_id}'"
            }
        except Exception as e:
            logger.error(f"Remove user from group failed for {phone}: {str(e)}")
            raise e
        finally:
            await client.disconnect()

async def download_message_media(phone: str, chat_id: int, message_id: int) -> str:
    """
    Download media from a specific message and return its local file path.
    """
    DOWNLOADS_DIR = "downloads"
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        try:
            # Fetch the specific message
            msg = await client.get_messages(int(chat_id), ids=int(message_id))
            if not msg or not msg.media:
                raise Exception("Message does not contain any media object.")
            
            # Check if a file with this prefix already exists (caching check)
            prefix = f"{phone}_{chat_id}_{message_id}"
            existing_files = [f for f in os.listdir(DOWNLOADS_DIR) if f.startswith(prefix)]
            if existing_files:
                return os.path.join(DOWNLOADS_DIR, existing_files[0])

            # Resolve extension
            from telethon.utils import get_extension
            ext = get_extension(msg.media) or ""
            
            # Define local save path
            local_filename = f"{phone}_{chat_id}_{message_id}{ext}"
            file_path = os.path.join(DOWNLOADS_DIR, local_filename)
            
            # Download file using Telethon (which may append appropriate extensions)
            actual_path = await client.download_media(msg, file=file_path)
            if not actual_path:
                raise Exception("Telethon download did not return a valid file path.")
            
            return actual_path
        except Exception as e:
            logger.error(f"Download media failed for {phone}: {str(e)}")
            raise e
        finally:
            await client.disconnect()

async def get_group_members(phone: str, chat_id: int, limit: int = 100):
    """
    Retrieve participants/members of a specific group or channel.
    """
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        try:
            entity = await client.get_entity(int(chat_id))
            participants = await client.get_participants(entity, limit=limit)
            
            members = []
            for u in participants:
                members.append({
                    "id": u.id,
                    "first_name": getattr(u, 'first_name', '') or '',
                    "last_name": getattr(u, 'last_name', '') or '',
                    "username": getattr(u, 'username', '') or '',
                    "phone": getattr(u, 'phone', '') or '',
                    "is_bot": getattr(u, 'bot', False),
                    "verified": getattr(u, 'verified', False),
                    "restricted": getattr(u, 'restricted', False)
                })
            return members
        except Exception as e:
            logger.error(f"Get group members failed for {phone}: {str(e)}")
            raise e
        finally:
            await client.disconnect()

async def get_forum_topics(phone: str, chat_id: int, limit: int = 100):
    """
    Retrieve list of forum topics from a supergroup.
    """
    from telethon.tl import functions
    client = get_client(phone)
    lock = get_lock(phone)
    async with lock:
        await client.start()
        try:
            entity = await client.get_entity(int(chat_id))
            result = await client(functions.channels.GetForumTopicsRequest(
                channel=entity,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=limit
            ))
            
            topics = []
            if result and hasattr(result, 'topics'):
                for t in result.topics:
                    topics.append({
                        "id": t.id,
                        "title": getattr(t, 'title', 'Unnamed Topic') or 'Unnamed Topic',
                        "icon_color": getattr(t, 'icon_color', None),
                        "closed": getattr(t, 'closed', False),
                        "pinned": getattr(t, 'pinned', False),
                        "top_message": getattr(t, 'top_message', None)
                    })
            return topics
        except Exception as e:
            logger.error(f"Get forum topics failed for {phone}: {str(e)}")
            raise e
        finally:
            await client.disconnect()