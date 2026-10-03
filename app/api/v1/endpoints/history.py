from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatConversation, ChatMessage
from app.db.session import get_db_session
from app.schemas.history import (
    ChatMessageCreate,
    ChatMessageResponse,
    ConversationCreate,
    ConversationResponse,
)

router = APIRouter()


def _auth_identity(request: Request) -> dict:
    return request.state.auth


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatConversation]:
    user_id = _auth_identity(request)["user_id"]
    result = await session.scalars(
        select(ChatConversation)
        .where(ChatConversation.user_id == user_id)
        .order_by(ChatConversation.updated_at.desc())
    )
    return list(result)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ChatConversation:
    identity = _auth_identity(request)
    conversation = ChatConversation(
        user_id=identity["user_id"],
        session_id=identity["session_id"],
        title=payload.title.strip() or "New conversation",
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


@router.get("/{conversation_id}/messages", response_model=list[ChatMessageResponse])
async def list_messages(
    conversation_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> list[ChatMessage]:
    user_id = _auth_identity(request)["user_id"]
    conversation = await session.scalar(
        select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    result = await session.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id, ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result)


@router.post(
    "/{conversation_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    conversation_id: UUID,
    payload: ChatMessageCreate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ChatMessage:
    identity = _auth_identity(request)
    conversation = await session.scalar(
        select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == identity["user_id"],
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    message = ChatMessage(
        conversation_id=conversation_id,
        user_id=identity["user_id"],
        role=payload.role,
        content=payload.content,
        citations=payload.citations,
        jwt_claims=identity["claims"],
    )
    conversation.updated_at = datetime.now(timezone.utc)
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message