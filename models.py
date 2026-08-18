from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime, date

class LoginRequest(BaseModel):
    phone_number: str = Field(..., example="+85500000000")

class CodeRequest(BaseModel):
    phone: str = Field(..., example="+855000000000")
    code: str = Field(..., example="12345")
    password: Optional[str] = None 
    phone_code_hash: str = Field(..., example="AB34EFGH5678")

class TokenResponse(BaseModel):
    access_token: str
    persistent: bool
    message: str

class MessageRequest(BaseModel):
    chat_id: int = Field(..., example=-4586738257)
    message: str = Field(..., example="Hello, this is a test message!")
    reply_to: Optional[int] = Field(None, description="Optional message/topic ID to reply to")

class FileMessageRequest(BaseModel):
    chat_id: int = Field(..., example=-4586738257)
    file_path: str = Field(..., example="C:/Users/HUN/Desktop/sample.jpg")
    caption: Optional[str] = None  # Optional caption
    reply_to: Optional[int] = Field(None, description="Optional message/topic ID to reply to")

class DeleteRequest(BaseModel):
    chat_id: int
    message_id: int

class DateRangeRequest(BaseModel):
    chat_id: int = Field(..., example="-4586738257")
    date_from: Optional[Union[datetime, date, str]] = Field(None, example="2023-01-01T00:00:00")
    date_to: Optional[Union[datetime, date, str]] = Field(None, example="2023-12-31T23:59:59")
    topic_id: Optional[int] = Field(None, example=7, description="Optional forum topic ID")

class UserSession(BaseModel):
    phone: str 
    telegram_session_active: bool
    last_verified: datetime

class Contact(BaseModel):
    id: int
    first_name: str
    last_name: str
    username: str
    phone: str
    mutual_contact: bool
    is_user: bool
    is_bot: bool
    status: str
    photo: Optional[dict]

class MessageOut(BaseModel):
    id: int
    date: Optional[datetime]
    text: Optional[str]
    sender_id: Optional[int]
    sender_name: Optional[str]
    media: bool
    reply_to: Optional[int]

class CreateShareRequest(BaseModel):
    chat_id: int
    topic_id: Optional[int] = None
    password: Optional[str] = None
    title: Optional[str] = None
    expires_in_hours: Optional[int] = None

class VerifyShareRequest(BaseModel):
    password: Optional[str] = None

class ShareMessageRequest(BaseModel):
    password: Optional[str] = None
    date_from: Optional[Union[datetime, date, str]] = None
    date_to: Optional[Union[datetime, date, str]] = None
    topic_id: Optional[int] = None


class MessageListResponse(BaseModel):
    chat_id: int
    total_messages: int
    messages: List[MessageOut]

class InviteRequest(BaseModel):
    chat_id: int = Field(..., example=-4586738257)
    user_id: str = Field(..., example="username_or_phone_or_id")

class RemoveUserRequest(BaseModel):
    chat_id: int = Field(..., example=-4586738257)
    user_id: str = Field(..., example="username_or_phone_or_id")