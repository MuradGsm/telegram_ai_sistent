from enum import Enum


class PlanTier(str, Enum):
    FREE = "free"
    START = "start"
    BUSINESS = "business"
    CUSTOM = "custom"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class DialogStatus(str, Enum):
    OPEN_AUTO = "open_auto"          
    ESCALATED = "escalated"         
    OPEN_HUMAN = "open_human"      
    CLOSED = "closed"
 
 
class MessageSender(str, Enum):
    CUSTOMER = "customer"
    BOT = "bot"
    OWNER = "owner"
    SYSTEM = "system"


class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class ChannelType(str, Enum):
    TELEGRAM = "telegram"
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    WEB = "web"