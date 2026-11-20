"""POST /chat endpoint supporting both JSON and SSE token-by-token streaming."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.loop import run_agent_turn
from app.agent.schemas import AgentTurnResult
from app.db.session import get_db_session

router = APIRouter(tags=["chat"])

USER_COOKIE_NAME = "compass_uid"
USER_HEADER_NAME = "X-Compass-User-Id"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
    stream: bool = False


def resolve_anonymous_user_id(request: Request) -> uuid.UUID:
    """Resolve persistent anonymous user ID from header or cookie, or mint a new UUID."""
    raw = request.headers.get(USER_HEADER_NAME) or request.cookies.get(USER_COOKIE_NAME)
    if raw:
        try:
            return uuid.UUID(raw.strip())
        except ValueError:
            pass
    return uuid.uuid4()


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/chat", response_model=AgentTurnResult)
async def chat_endpoint(
    payload: ChatRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> Any:
    user_id = resolve_anonymous_user_id(request)
    wants_stream = payload.stream or ("text/event-stream" in request.headers.get("accept", ""))

    if not wants_stream:
        result = await run_agent_turn(
            session=session,
            user_id=user_id,
            user_message=payload.message,
            conversation_id=payload.conversation_id,
        )
        response.set_cookie(
            key=USER_COOKIE_NAME,
            value=str(user_id),
            max_age=60 * 60 * 24 * 180,
            httponly=False,
            samesite="lax",
        )
        response.headers[USER_HEADER_NAME] = str(user_id)
        return result

    async def event_stream() -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def push_status(label: str) -> None:
            await queue.put(_sse_event("status", {"message": label}))

        async def worker() -> None:
            try:
                result = await run_agent_turn(
                    session=session,
                    user_id=user_id,
                    user_message=payload.message,
                    conversation_id=payload.conversation_id,
                    on_status=push_status,
                )
                # Stream mentor reply smoothly word-by-word so UI feels responsive and alive
                words = result.reply.split(" ")
                for idx, word in enumerate(words):
                    token = word if idx == 0 else " " + word
                    await queue.put(_sse_event("token", {"token": token}))
                    await asyncio.sleep(0.012)

                await queue.put(
                    _sse_event(
                        "meta",
                        {
                            "conversation_id": str(result.conversation_id),
                            "user_id": str(result.user_id),
                            "suggested_replies": result.suggested_replies,
                            "recommended_jobs": [
                                j.model_dump(mode="json") for j in result.recommended_jobs
                            ],
                            "skill_gap": (
                                result.skill_gap.model_dump(mode="json")
                                if result.skill_gap
                                else None
                            ),
                            "roadmap": (
                                result.roadmap.model_dump(mode="json") if result.roadmap else None
                            ),
                            "profile": (
                                result.profile.model_dump(mode="json") if result.profile else None
                            ),
                            "tool_trace": [t.model_dump(mode="json") for t in result.tool_trace],
                        },
                    )
                )
                await queue.put(_sse_event("done", {"ok": True}))
            except Exception as exc:
                await queue.put(_sse_event("error", {"message": str(exc)}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(worker())
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            if not task.done():
                task.cancel()

    stream_resp = StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            USER_HEADER_NAME: str(user_id),
        },
    )
    stream_resp.set_cookie(
        key=USER_COOKIE_NAME,
        value=str(user_id),
        max_age=60 * 60 * 24 * 180,
        httponly=False,
        samesite="lax",
    )
    return stream_resp
