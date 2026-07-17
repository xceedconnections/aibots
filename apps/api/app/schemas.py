from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from app.models import ActionType, CallStatus


# ---- Auth ----
class LoginRequest(BaseModel):
    # Plain str — allow admin@aibots.local (EmailStr rejects .local reserved TLD)
    email: str = Field(min_length=3, max_length=255)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool

    class Config:
        from_attributes = True


# ---- Answers ----
class AnswerCreate(BaseModel):
    intent: str
    keywords: list[str] = Field(default_factory=list)
    next_question_id: Optional[int] = None
    action: ActionType = ActionType.CONTINUE
    store_value: Optional[str] = None
    priority: int = 0


class AnswerUpdate(BaseModel):
    intent: Optional[str] = None
    keywords: Optional[list[str]] = None
    next_question_id: Optional[int] = None
    action: Optional[ActionType] = None
    store_value: Optional[str] = None
    priority: Optional[int] = None


class AnswerOut(AnswerCreate):
    id: int
    question_id: int

    class Config:
        from_attributes = True


# ---- Questions ----
class QuestionCreate(BaseModel):
    prompt: str
    sort_order: int = 0
    variable_name: Optional[str] = None
    timeout_ms: int = 8000
    max_retries: int = 2
    is_start: bool = False
    answers: list[AnswerCreate] = Field(default_factory=list)


class QuestionUpdate(BaseModel):
    prompt: Optional[str] = None
    sort_order: Optional[int] = None
    variable_name: Optional[str] = None
    timeout_ms: Optional[int] = None
    max_retries: Optional[int] = None
    is_start: Optional[bool] = None


class QuestionOut(BaseModel):
    id: int
    bot_id: int
    prompt: str
    sort_order: int
    variable_name: Optional[str]
    timeout_ms: int
    max_retries: int
    is_start: bool
    answers: list[AnswerOut] = []

    class Config:
        from_attributes = True


# ---- Bots ----
class BotCreate(BaseModel):
    name: str
    campaign: str
    transfer_campaign: str
    language: str = "en"
    voice: str = "en_US-lessac-medium"
    model: str = "qwen2.5:7b-instruct"
    temperature: float = 0.2
    greeting: str = "Hello, thank you for taking our call."
    active: bool = True
    description: Optional[str] = None


class BotUpdate(BaseModel):
    name: Optional[str] = None
    campaign: Optional[str] = None
    transfer_campaign: Optional[str] = None
    language: Optional[str] = None
    voice: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    greeting: Optional[str] = None
    active: Optional[bool] = None
    description: Optional[str] = None


class BotOut(BotCreate):
    id: int
    created_at: datetime
    updated_at: datetime
    questions: list[QuestionOut] = []

    class Config:
        from_attributes = True


class BotListItem(BaseModel):
    id: int
    name: str
    campaign: str
    transfer_campaign: str
    language: str
    voice: str
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Calls / Webhooks ----
class VicidialStartPayload(BaseModel):
    call_id: Optional[str] = None
    lead_id: Optional[str] = None
    phone: Optional[str] = None
    campaign: Optional[str] = None
    bot_id: Optional[int] = None
    uniqueid: Optional[str] = None
    channel: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class CallTurnRequest(BaseModel):
    call_session_id: int
    transcript: str


class DecisionResult(BaseModel):
    action: ActionType
    intent: Optional[str] = None
    confidence: float = 0.0
    reply_text: str
    next_question_id: Optional[int] = None
    variables: dict[str, Any] = Field(default_factory=dict)
    transfer_campaign: Optional[str] = None
    done: bool = False


class CallSessionOut(BaseModel):
    id: int
    bot_id: Optional[int]
    vicidial_call_id: Optional[str]
    lead_id: Optional[str]
    phone: Optional[str]
    campaign: Optional[str]
    status: CallStatus
    current_question_id: Optional[int]
    variables: dict
    transcript: list
    transfer_campaign: Optional[str]
    duration_seconds: int
    started_at: datetime
    ended_at: Optional[datetime]

    class Config:
        from_attributes = True


class CallStartResponse(BaseModel):
    call_session_id: int
    bot_id: int
    greeting: str
    first_question: Optional[str] = None
    first_question_id: Optional[int] = None
    status: CallStatus


class DashboardStats(BaseModel):
    bots_total: int
    bots_active: int
    calls_today: int
    transfers_today: int
    qualified_today: int
    rejected_today: int
    avg_duration_seconds: float
    qualification_rate: float
