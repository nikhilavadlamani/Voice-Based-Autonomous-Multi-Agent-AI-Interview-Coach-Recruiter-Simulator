import base64
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.schemas import SessionCreateRequest, SessionCreateResponse, TranscriptTurn
from app.services.session_manager import session_manager
from app.services.stt_service import stt_service
from app.services.tts_service import tts_service

router = APIRouter(tags=["sessions"])


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(payload: SessionCreateRequest) -> SessionCreateResponse:
    session = session_manager.create_session(
        candidate_id=payload.candidate_id,
        role=payload.role,
        interview_mode=payload.interview_mode,
        domain_focus=payload.domain_focus,
    )
    greeting = session_manager.greeting(session.session_id)
    return SessionCreateResponse(session_id=session.session_id, **greeting)


@router.get("/sessions/{session_id}/report")
async def get_report(session_id: str):
    return session_manager.build_report(session_id)


@router.websocket("/ws/interview/{session_id}")
async def interview_socket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        while True:
            raw_message = await websocket.receive_text()
            payload = json.loads(raw_message)
            event_type = payload.get("type")

            if event_type == "candidate_text":
                candidate_text = payload["text"]
            elif event_type == "candidate_audio":
                candidate_text = await stt_service.transcribe_bytes(
                    base64.b64decode(payload["audio"]),
                    filename=payload.get("filename", "chunk.webm"),
                )
            else:
                await websocket.send_json({"type": "error", "message": f"Unsupported event type: {event_type}"})
                continue

            session_manager.append_turn(
                session_id,
                TranscriptTurn(speaker="candidate", text=candidate_text, metadata={"source": event_type}),
            )
            outcome = session_manager.process_candidate_turn(session_id, candidate_text)
            session_manager.append_turn(
                session_id,
                TranscriptTurn(
                    speaker="agent",
                    agent=outcome["active_agent"],
                    text=outcome["agent_response"],
                    metadata={"feedback_notes": outcome["feedback_notes"]},
                ),
            )
            await websocket.send_json(
                {
                    "type": "agent_turn",
                    "agent": outcome["active_agent"],
                    "text": outcome["agent_response"],
                    "feedback_notes": outcome["feedback_notes"],
                    "should_end": outcome["should_end"],
                    "audio_base64": tts_service.synthesize(outcome["agent_response"], outcome["active_agent"]),
                }
            )
            if outcome["should_end"]:
                report = session_manager.build_report(session_id)
                await websocket.send_json({"type": "final_report", "report": report.model_dump()})
                break
    except WebSocketDisconnect:
        return
