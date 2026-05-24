from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from telegram_client import *
from models import *
from auth import *
from typing import Optional
import logging
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from chat_types import ChatType
from fastapi import Query

import os

from fastapi.middleware.cors import CORSMiddleware



logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

security = HTTPBearer()

app = FastAPI(
    title="Telegram Management API",
    version="1.0.0",
    description="Manage Telegram login, contacts, chats, and messages with FastAPI",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specifically "https://a1f80e1f-e0c5-4f4a-918a-ab3f16b01e69.lovableproject.com"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Jinja2 templates engine
templates = Jinja2Templates(directory="web")

# Route that serves HTML content
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "name": "Home"})
# --- Path Setup ---
BASE_DIR = Path(__file__).parent
BUILD_PATH = BASE_DIR / "telegram-dashboard" / "build"

# --- React Integration Logic ---
if BUILD_PATH.exists():
    print("✅ Build folder found")
    
    # 1. Serve the 'static' folder (CSS/JS) 
    # React expects these at /static/...
    if (BUILD_PATH / "static").exists():
        app.mount("/static", StaticFiles(directory=BUILD_PATH / "static"), name="static")

    # # 2. FIX: Redirect root to /web
    # @app.get("/")
    # async def redirect_to_web():
    #     return RedirectResponse(url="/web")

    # 3. Serve React App at /web
    @app.get("/web/{path:path}")
    @app.get("/web")
    async def serve_react(path: str = ""):
        index_file = BUILD_PATH / "index.html"
        
        # Check if requesting a specific file (like manifest.json or logo.png)
        file_request = BUILD_PATH / path
        if path and file_request.exists() and file_request.is_file():
            return FileResponse(file_request)
            
        # Otherwise, return index.html to support React Router (Client-side routing)
        if index_file.exists():
            return FileResponse(index_file)
            
        return JSONResponse({"error": "index.html not found"}, status_code=404)

else:
    print(f"❌ Build folder NOT found at: {BUILD_PATH}")
    
    @app.get("/")
    async def root():
        return {
            "message": "FastAPI is running",
            "error": "React build folder not found",
            "expected_path": str(BUILD_PATH)
        }
    
    
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth[7:]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
                if not await is_session_active(payload["phone"]):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Telegram session expired"}
                    )
            except:
                pass
    return await call_next(request)

@app.post("/login", tags=["Telegram Auth"])
async def login_phone(req: LoginRequest):
    try:
        result = await login(req.phone_number)
        return {
            "message": "Code sent to Telegram",
            "phone_code_hash": result["phone_code_hash"]
        }
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/verify", tags=["Telegram Auth"])
async def verify_code_route(req: CodeRequest):
    try:
        result = await verify_code(
            phone=req.phone,
            code=req.code,
            password=req.password,
            phone_code_hash=req.phone_code_hash
        )
        return TokenResponse(**result)
    except Exception as e:
        logger.error(f"Verification error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/telegram/status", tags=["Telegram Auth"])
async def telegram_status(user: dict = Depends(get_current_user)):
    try:
        me = await get_me(user["phone"])
        return {
            "is_logged_in": bool(me),
            "user": me["user"]["username"] if me else None
        }
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/logout", tags=["Telegram Auth"])
async def logout_route(
    user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        await logout(user["phone"])
        return await logout_user(credentials.credentials)
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/renew-token", tags=["Telegram Auth"])
async def renew_token(user: dict = Depends(get_current_user)):
    from datetime import datetime
    try:
        phone = user["phone"]
        token_payload = {
            "phone": phone,
            "created_at": datetime.utcnow().isoformat()
        }
        token = create_token(token_payload)
        
        try:
            client = get_client(phone)
            lock = get_lock(phone)
            async with lock:
                await client.connect()
                if await client.is_user_authorized():
                    message = (
                        f"🔄 *Renewed Persistent API Token* 🔄\n\n"
                        f"This new token will work until:\n"
                        f"1. You log out of Telegram\n"
                        f"2. Delete this session\n\n"
                        f"Token: `{token}`\n"
                        f"Account: {phone}\n\n"
                        f"⚠️ Keep this secure - it won't expire automatically"
                    )
                    await client.send_message("me", message, parse_mode='markdown')
        except Exception as telegram_error:
            logger.error(f"Failed to send renewed token to Telegram Saved Messages: {str(telegram_error)}")
            
        return {
            "access_token": token,
            "persistent": True,
            "message": "Token renewed successfully and saved to Telegram saved messages"
        }
    except Exception as e:
        logger.error(f"Token renewal error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/me", tags=["Telegram User"])
async def me_route(user: dict = Depends(get_current_user)):
    try:
        result = await get_me(user["phone"])
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return result
    except Exception as e:
        logger.error(f"Get me error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-contacts", tags=["Telegram User"])
async def get_contacts_route(user: dict = Depends(get_current_user)):
    try:
        contacts = await get_contacts(user["phone"])
        if not contacts:
            return {"message": "No contacts found", "contacts": []}
        return {"contacts": contacts}
    except Exception as e:
        logger.error(f"Contacts error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/list-chats", tags=["Telegram Chats"])
async def get_chats_route(user: dict = Depends(get_current_user)):
    try:
        return await get_dialogs(user["phone"])
    except Exception as e:
        logger.error(f"Chats error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/chats/list-own", tags=["Telegram Chats"])
async def get_own_chats_route(user: dict = Depends(get_current_user)):
    """
    List all groups and channels created/owned by the authenticated user.
    """
    try:
        return await get_own_groups(user["phone"])
    except Exception as e:
        logger.error(f"Get own chats error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chats/message/send", tags=["Telegram Chats"])
async def send_message_route(
    req: MessageRequest,
    user: dict = Depends(get_current_user)
):
    try:
        return await send_message(user["phone"], req.chat_id, req.message)
    except Exception as e:
        logger.error(f"Send message error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chats/message/send-file", tags=["Telegram Chats"])
async def send_file_route(
    req: FileMessageRequest,
    user: dict = Depends(get_current_user)
):
    """
    Send a file with optional caption to a Telegram chat.
    """
    try:
        return await send_file_message(user["phone"], req.chat_id, req.file_path, req.caption)
    except Exception as e:
        logger.error(f"Send file error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chats/message/delete", tags=["Telegram Chats"])
async def delete_message_route(
    req: DeleteRequest,
    user: dict = Depends(get_current_user)
):
    try:
        return await delete_message(user["phone"], req.chat_id, req.message_id)
    except Exception as e:
        logger.error(f"Delete message error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chats/invite", tags=["Telegram Chats"])
async def invite_to_group_route(
    req: InviteRequest,
    user: dict = Depends(get_current_user)
):
    """
    Invite or add a user to a group or channel.
    `user_id` can be a username, a phone number, or a numeric user ID.
    """
    try:
        return await invite_to_group(user["phone"], req.chat_id, req.user_id)
    except Exception as e:
        logger.error(f"Invite user error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chats/remove-user", tags=["Telegram Chats"])
async def remove_user_route(
    req: RemoveUserRequest,
    user: dict = Depends(get_current_user)
):
    """
    Remove or kick a user from a group or channel.
    `user_id` can be a username, a phone number, or a numeric user ID.
    """
    try:
        return await remove_from_group(user["phone"], req.chat_id, req.user_id)
    except Exception as e:
        logger.error(f"Remove user error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get(
    "/chats/list-messages/{chat_type}",
    tags=["Telegram Chats"],
    response_model=MessageListResponse
)
async def list_messages(
    chat_type: ChatType,                      # ✅ typed enum
    chat_id: int = Query(..., example=6832518961),
    limit: int = Query(35, description="Limit the number of messages to load"),
    user: dict = Depends(get_current_user)
):
    try:
        if chat_type == ChatType.all:
            messages = await list_all_messages(user["phone"], chat_id, limit=limit)

        elif chat_type == ChatType.media:
            messages = [
                m for m in await list_all_messages(user["phone"], chat_id, limit=limit)
                if m["media"]
            ]

        elif chat_type == ChatType.text:
            messages = [
                m for m in await list_all_messages(user["phone"], chat_id, limit=limit)
                if m["text"]
            ]

        else:
            raise HTTPException(status_code=400, detail="Invalid chat type")

        return {
            "chat_id": chat_id,
            "total_messages": len(messages),
            "messages": messages
        }

    except Exception as e:
        logger.error(f"List messages error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/chats/list-message/by-date", tags=["Telegram Chats"])
async def get_messages_by_date(
    req: DateRangeRequest,
    user: dict = Depends(get_current_user)
):
    try:
        # Call fetch_messages from telegram_client.py
        messages = await fetch_messages(
            phone=user["phone"],
            chat_id=req.chat_id,
            date_from=req.date_from,
            date_to=req.date_to
        )
        return {"messages": messages}
    except Exception as e:
        logger.error(f"Messages by date error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/chats/media/download", tags=["Telegram Chats"])
async def download_media_route(
    chat_id: int = Query(..., description="The chat ID where the message is located"),
    message_id: int = Query(..., description="The message ID that contains the media"),
    user: dict = Depends(get_current_user)
):
    """
    Download or stream media from a specific message ID in a specific chat.
    Uses local caching to avoid repeated downloads from Telegram API.
    """
    try:
        file_path = await download_message_media(user["phone"], chat_id, message_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Media file not found after download.")
        return FileResponse(file_path)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Download media route error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))