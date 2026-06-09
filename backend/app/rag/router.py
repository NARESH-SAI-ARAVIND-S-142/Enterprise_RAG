"""
DocuMind 2.0 — Chat Router
WebSocket streaming + REST fallback for RAG conversations.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.auth.models import User
from app.auth.utils import get_current_user, verify_ws_token
from app.database import get_db, async_session_maker
from app.documents.models import ChatMessage, ChatSession
from app.documents.schemas import (
    ChatMessageResponse,
    ChatQueryRequest,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    MessageFeedbackRequest,
)
from app.rag.graph import get_rag_graph, run_rag_pipeline
from app.rag.memory import conversation_memory

router = APIRouter()


# ── WebSocket Streaming ───────────────────────────────────────
@router.websocket("/ws/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time streaming chat.
    JWT is passed as query param since WS can't use Authorization headers.
    """
    # Authenticate
    async with async_session_maker() as db:
        user = await verify_ws_token(token, db)
        if not user:
            await websocket.close(code=4001, reason="Unauthorized")
            return

        # Verify session belongs to user
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            await websocket.close(code=4004, reason="Session not found")
            return

    await websocket.accept()
    logger.info(f"WebSocket connected: session={session_id}, user={user.id}")

    try:
        while True:
            data = await websocket.receive_json()
            query = data.get("query", "").strip()
            document_ids = data.get("document_ids", [])
            model = data.get("model")
            provider = data.get("provider")

            if not query:
                await websocket.send_json({"type": "error", "content": "Empty query"})
                continue

            # Send thinking status
            await websocket.send_json({"type": "status", "content": "Analyzing query..."})

            try:
                async with async_session_maker() as db:
                    # Get conversation context
                    chat_history = await conversation_memory.get_context_for_query(
                        session_id, query, db
                    )

                    # Send retrieval status
                    await websocket.send_json({"type": "status", "content": "Retrieving documents..."})

                    # Run RAG pipeline
                    graph = get_rag_graph()
                    initial_state = {
                        "query": query,
                        "user_id": user.id,
                        "document_ids": document_ids,
                        "chat_history": chat_history,
                        "model": model,
                        "provider": provider,
                        "rewritten_queries": [],
                        "retrieved_chunks": [],
                        "context_sufficient": False,
                        "answer_draft": "",
                        "faithfulness_score": 0.0,
                        "iteration_count": 0,
                        "final_answer": "",
                        "citations": [],
                        "confidence_score": 0.0,
                        "retrieval_metadata": {},
                    }

                    # Stream graph execution events
                    async for event in graph.astream_events(initial_state, version="v2"):
                        event_name = event.get("event", "")
                        name = event.get("name", "")

                        if event_name == "on_chain_start":
                            status_map = {
                                "rewrite_query": "Rewriting query...",
                                "retrieve": "Retrieving documents...",
                                "grade_relevance": "Grading relevance...",
                                "generate": "Generating answer...",
                                "check_faithfulness": "Checking faithfulness...",
                                "refine_answer": "Refining answer...",
                                "format_citations": "Formatting citations...",
                            }
                            if name in status_map:
                                await websocket.send_json({
                                    "type": "status",
                                    "content": status_map[name],
                                })

                        elif event_name == "on_chat_model_stream":
                            chunk_content = event.get("data", {}).get("chunk", None)
                            if chunk_content and hasattr(chunk_content, "content"):
                                await websocket.send_json({
                                    "type": "token",
                                    "content": chunk_content.content,
                                })

                        elif event_name == "on_chain_end" and name == "retrieve":
                            output = event.get("data", {}).get("output", {})
                            chunks = output.get("retrieved_chunks", [])
                            await websocket.send_json({
                                "type": "sources",
                                "content": [c.to_dict() for c in chunks if hasattr(c, "to_dict")],
                            })

                        elif event_name == "on_chain_end" and name == "check_faithfulness":
                            output = event.get("data", {}).get("output", {})
                            score = output.get("faithfulness_score", 0)
                            await websocket.send_json({
                                "type": "confidence",
                                "content": score,
                            })

                    # Get final state from non-streaming invoke as fallback
                    final_state = await graph.ainvoke(initial_state)
                    final_answer = final_state.get("final_answer", "I couldn't generate an answer.")
                    citations = final_state.get("citations", [])
                    confidence = final_state.get("confidence_score", 0.0)
                    faithfulness = final_state.get("faithfulness_score", 0.0)

                    # Send final answer (in case streaming missed tokens)
                    await websocket.send_json({
                        "type": "answer",
                        "content": final_answer,
                    })
                    await websocket.send_json({
                        "type": "sources",
                        "content": citations,
                    })
                    await websocket.send_json({
                        "type": "confidence",
                        "content": confidence,
                    })

                    # Save messages to DB
                    user_msg = ChatMessage(
                        session_id=session_id,
                        role="user",
                        content=query,
                    )
                    assistant_msg = ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=final_answer,
                        citations=json.dumps(citations),
                        confidence_score=confidence,
                        faithfulness_score=faithfulness,
                        model_used=model or "default",
                    )
                    db.add(user_msg)
                    db.add(assistant_msg)
                    await db.commit()

                    # Signal completion
                    await websocket.send_json({"type": "done"})

            except Exception as e:
                logger.error(f"RAG pipeline error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "content": f"An error occurred: {str(e)}",
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session={session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


# ── REST Fallback ──────────────────────────────────────────────
@router.post("/query")
async def chat_query(
    request: ChatQueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """REST fallback for chat — returns complete answer (no streaming)."""
    final_state = await run_rag_pipeline(
        query=request.query,
        user_id=current_user.id,
        document_ids=request.document_ids,
        model=request.model,
        provider=request.provider,
    )

    return {
        "answer": final_state.get("final_answer", ""),
        "citations": final_state.get("citations", []),
        "confidence_score": final_state.get("confidence_score", 0.0),
        "retrieval_metadata": final_state.get("retrieval_metadata", {}),
    }


# ── Session Management ────────────────────────────────────────
@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(
    request: ChatSessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    session = ChatSession(
        user_id=current_user.id,
        title=request.title,
        document_ids=json.dumps(request.document_ids),
    )
    db.add(session)
    await db.flush()
    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        document_ids=request.document_ids,
        messages=[],
        created_at=session.created_at,
    )


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's chat sessions."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": str(s.created_at),
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all messages in a chat session."""
    # Verify session belongs to user
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()

    return [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "citations": json.loads(msg.citations) if msg.citations else [],
            "confidence_score": msg.confidence_score,
            "faithfulness_score": msg.faithfulness_score,
            "model_used": msg.model_used,
            "feedback": msg.feedback,
            "created_at": str(msg.created_at),
        }
        for msg in messages
    ]


@router.post("/messages/{message_id}/feedback")
async def submit_feedback(
    message_id: str,
    request: MessageFeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit thumbs up/down feedback on a message."""
    result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    message.feedback = request.feedback
    await db.flush()

    return {"message": "Feedback recorded", "feedback": request.feedback}


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat session and all its messages."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
    logger.info(f"Deleted chat session {session_id}")
