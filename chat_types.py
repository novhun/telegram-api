from enum import Enum

class ChatType(str, Enum):
    all = "all"
    media = "media"
    text = "text"
