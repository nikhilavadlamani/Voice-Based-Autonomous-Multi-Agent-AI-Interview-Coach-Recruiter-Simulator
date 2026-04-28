from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.agents.graph import interview_graph
from app.core.config import settings
from app.models.schemas import SessionReport, SessionSummary, TranscriptTurn
from app.services.rag_service import rag_service
from app.services.scoring_service import scoring_service


@dataclass
class SessionState:
    session_id: str
    candidate_id: str
    role: str
    interview_mode: str
    domain_focus: list[str]
    transcript: list[TranscriptTurn] = field(default_factory=list)
    graph_state: dict[str, Any] = field(default_factory=dict)
    status: str = "ready"


class SessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionState] = {}

    def create_session(self, candidate_id: str, role: str, interview_mode: str, domain_focus: list[str]) -> SessionState:
        session_id = str(uuid.uuid4())
        resume_profile = rag_service.get_profile(candidate_id)
        resume_context = rag_service.retrieve_context(candidate_id, f"Summarize candidate fit for {role}")
        session = SessionState(
            session_id=session_id,
            candidate_id=candidate_id,
            role=role,
            interview_mode=interview_mode,
            domain_focus=domain_focus,
            graph_state={
                "session_id": session_id,
                "candidate_id": candidate_id,
                "role": role,
                "interview_mode": interview_mode,
                "domain_focus": domain_focus,
                "turn_count": 0,
                "active_agent": "hr",
                "next_action": "ask_follow_up",
                "difficulty": "medium",
                "conversation_history": [],
                "resume_context": resume_context,
                "resume_summary": resume_profile.get("summary", ""),
                "resume_highlights": resume_profile.get("highlights", []),
                "evaluation_notes": [],
                "confidence_score": 0.5,
                "communication_score": 0.5,
                "technical_score": 0.5,
                "problem_solving_score": 0.5,
                "should_end": False,
                "answer_signal": "mixed",
                "focus_recommendation": "Answer with specific examples and measurable impact.",
                "planner_rationale": "",
            },
            status="live",
        )
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> SessionState:
        return self.sessions[session_id]

    def append_turn(self, session_id: str, turn: TranscriptTurn) -> None:
        session = self.get_session(session_id)
        session.transcript.append(turn)
        session.graph_state.setdefault("conversation_history", []).append(turn.model_dump())

    def process_candidate_turn(self, session_id: str, answer: str) -> dict[str, Any]:
        session = self.get_session(session_id)
        session.graph_state["latest_candidate_answer"] = answer
        session.graph_state["turn_count"] = session.graph_state.get("turn_count", 0) + 1
        result = interview_graph.invoke(session.graph_state)
        session.graph_state.update(result)

        active_agent = session.graph_state.get("active_agent", "technical")
        agent_response = session.graph_state.get("last_agent_response", "Could you expand on that?")
        if session.graph_state.get("should_end"):
            active_agent = "hiring_manager"
            agent_response = "We have enough signal for today. I am wrapping up the interview and generating your report."
            session.status = "completed"

        return {
            "active_agent": active_agent,
            "agent_response": agent_response,
            "feedback_notes": session.graph_state.get("evaluation_notes", [])[-2:],
            "should_end": session.graph_state.get("should_end", False),
            "latest_signal": session.graph_state.get("answer_signal", "mixed"),
            "focus_recommendation": session.graph_state.get("focus_recommendation", ""),
        }

    def build_report(self, session_id: str) -> SessionReport:
        session = self.get_session(session_id)
        report = session.graph_state.get("final_report")
        if not report:
            report = scoring_service.finalize_report(session.graph_state)
            session.graph_state["final_report"] = report

        return SessionReport(
            session_id=session_id,
            final_recommendation=report.get("final_recommendation", "mixed"),
            scorecard=report["scorecard"],
            strengths=report.get("strengths", []),
            weaknesses=report.get("weaknesses", []),
            improvement_roadmap=report.get("improvement_roadmap", []),
            transcript=session.transcript,
        )

    def greeting(self, session_id: str) -> dict[str, str]:
        session = self.get_session(session_id)
        highlights = session.graph_state.get("resume_highlights", [])
        resume_hook = f" I noticed {highlights[0]}." if highlights else ""
        greeting = (
            f"Hi, I'm Maya. I'll be guiding this {session.role} interview today.{resume_hook} "
            "We'll start with your background, spend some time on technical depth, and then wrap up with a hiring-manager style close. "
            "Whenever you're ready, introduce yourself the way you would in a real interview and start with the experience that feels most relevant here."
        )
        return {"first_speaker": "hr", "greeting": greeting}

    def session_summary(self, session_id: str) -> SessionSummary:
        session = self.get_session(session_id)
        return SessionSummary(
            session_id=session.session_id,
            role=session.role,
            interview_mode=session.interview_mode,
            turn_count=session.graph_state.get("turn_count", 0),
            active_agent=session.graph_state.get("active_agent", "hr"),
            difficulty=session.graph_state.get("difficulty", "medium"),
            status=session.status if session.status in {"ready", "live", "completed", "closed"} else "live",
            latest_signal=session.graph_state.get("answer_signal", "mixed"),
            focus_recommendation=session.graph_state.get("focus_recommendation", ""),
        )

    def close_session(self, session_id: str) -> SessionSummary:
        session = self.get_session(session_id)
        session.status = "closed"
        return self.session_summary(session_id)

    def reset_session(self, session_id: str) -> SessionSummary:
        session = self.get_session(session_id)
        session.transcript.clear()
        session.graph_state.update(
            {
                "turn_count": 0,
                "active_agent": "hr",
                "next_action": "ask_follow_up",
                "difficulty": "medium",
                "conversation_history": [],
                "evaluation_notes": [],
                "confidence_score": 0.5,
                "communication_score": 0.5,
                "technical_score": 0.5,
                "problem_solving_score": 0.5,
                "should_end": False,
                "answer_signal": "mixed",
                "focus_recommendation": "Answer with specific examples and measurable impact.",
                "planner_rationale": "",
            }
        )
        session.status = "live"
        session.graph_state.pop("final_report", None)
        session.graph_state.pop("latest_candidate_answer", None)
        session.graph_state.pop("last_agent_response", None)
        return self.session_summary(session_id)


session_manager = SessionManager()
