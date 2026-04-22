from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agents.prompts import (
    FEEDBACK_SYSTEM_PROMPT,
    HIRING_MANAGER_SYSTEM_PROMPT,
    HR_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    TECHNICAL_SYSTEM_PROMPT,
)
from app.agents.state import InterviewState
from app.core.config import settings
from app.services.scoring_service import scoring_service


def _llm() -> ChatOpenAI | None:
    if not settings.openai_api_key:
        return None
    return ChatOpenAI(model=settings.openai_model, temperature=0.35, api_key=settings.openai_api_key)


def _invoke_with_fallback(system_prompt: str, prompt: str, fallback_text: str) -> str:
    llm = _llm()
    if llm is None:
        return fallback_text
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prompt)])
    return response.content if isinstance(response.content, str) else str(response.content)


def _history_as_text(history: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{item.get('speaker', 'unknown')}::{item.get('agent', 'candidate')} -> {item.get('text', '')}"
        for item in history[-10:]
    )


def planner_node(state: InterviewState) -> InterviewState:
    history = _history_as_text(state.get("conversation_history", []))
    answer = state.get("latest_candidate_answer", "")
    score_snapshot = {
        "technical": state.get("technical_score", 0.5),
        "communication": state.get("communication_score", 0.5),
        "confidence": state.get("confidence_score", 0.5),
        "problem_solving": state.get("problem_solving_score", 0.5),
    }
    planner_prompt = f"""
Resume context:
{state.get('resume_context', 'No resume context available.')}

Interview mode: {state.get('interview_mode', 'coaching')}
Role: {state.get('role', '')}
Current difficulty: {state.get('difficulty', 'medium')}
Turn count: {state.get('turn_count', 0)}
Recent history:
{history}

Latest candidate answer:
{answer}

Current scores:
{json.dumps(score_snapshot)}

Return JSON with keys:
active_agent, next_action, difficulty, should_end, rationale
"""
    llm = _llm()
    if llm is None:
        turn_count = state.get("turn_count", 0)
        decision = {
            "active_agent": "hr" if turn_count <= 1 else "technical" if turn_count <= 3 else "hiring_manager",
            "next_action": "ask_follow_up",
            "difficulty": "hard" if state.get("technical_score", 0.5) > 0.75 else "medium",
            "should_end": turn_count >= settings.max_turns_per_session,
            "rationale": "Fallback planner selected a deterministic interview progression because no LLM key is configured.",
        }
    else:
        response = llm.invoke([SystemMessage(content=PLANNER_SYSTEM_PROMPT), HumanMessage(content=planner_prompt)])
        try:
            decision = json.loads(response.content)
        except json.JSONDecodeError:
            decision = {
                "active_agent": "technical",
                "next_action": "ask_follow_up",
                "difficulty": state.get("difficulty", "medium"),
                "should_end": False,
                "rationale": response.content,
            }

    state["active_agent"] = decision.get("active_agent", "technical")
    state["next_action"] = decision.get("next_action", "ask_follow_up")
    state["difficulty"] = decision.get("difficulty", state.get("difficulty", "medium"))
    state["should_end"] = bool(decision.get("should_end", False)) or (
        state.get("turn_count", 0) >= settings.max_turns_per_session
    )
    state.setdefault("evaluation_notes", []).append(f"Planner: {decision.get('rationale', '')}")
    return state


def confidence_node(state: InterviewState) -> InterviewState:
    metrics = scoring_service.estimate_confidence(state.get("latest_candidate_answer", ""))
    state["confidence_score"] = metrics["confidence_score"]
    state["communication_score"] = metrics["communication_clarity"]
    state.setdefault("evaluation_notes", []).append(metrics["note"])
    return state


def hr_node(state: InterviewState) -> InterviewState:
    prompt = f"""
Candidate role target: {state.get('role')}
Resume context:
{state.get('resume_context', '')}

Recent interview:
{_history_as_text(state.get('conversation_history', []))}

Ask the next HR question or deliver a concise HR-oriented follow-up.
"""
    state["last_agent_response"] = _invoke_with_fallback(
        HR_SYSTEM_PROMPT,
        prompt,
        "Tell me about your background, the most relevant AI systems you've shipped, and the business impact you owned.",
    )
    return state


def technical_node(state: InterviewState) -> InterviewState:
    prompt = f"""
Role: {state.get('role')}
Difficulty: {state.get('difficulty', 'medium')}
Focus areas: {', '.join(state.get('domain_focus', []))}
Resume context:
{state.get('resume_context', '')}

Recent history:
{_history_as_text(state.get('conversation_history', []))}

Ask one technical question or follow-up with production-grade realism.
"""
    state["last_agent_response"] = _invoke_with_fallback(
        TECHNICAL_SYSTEM_PROMPT,
        prompt,
        "Design a production ML interview copilot for low latency and high reliability. Walk through architecture, failure modes, and tradeoffs.",
    )
    return state


def hiring_manager_node(state: InterviewState) -> InterviewState:
    prompt = f"""
Role: {state.get('role')}
Scores:
technical={state.get('technical_score', 0.5)}
communication={state.get('communication_score', 0.5)}
confidence={state.get('confidence_score', 0.5)}
problem_solving={state.get('problem_solving_score', 0.5)}

Recent history:
{_history_as_text(state.get('conversation_history', []))}

Ask a final-round question or summarize decision-ready concerns.
"""
    state["last_agent_response"] = _invoke_with_fallback(
        HIRING_MANAGER_SYSTEM_PROMPT,
        prompt,
        "What would you prioritize in your first 90 days to improve interview quality, candidate experience, and recruiter efficiency?",
    )
    return state


def feedback_node(state: InterviewState) -> InterviewState:
    prompt = f"""
Interview mode: {state.get('interview_mode', 'coaching')}
Latest answer: {state.get('latest_candidate_answer', '')}
Scores:
technical={state.get('technical_score', 0.5)}
communication={state.get('communication_score', 0.5)}
confidence={state.get('confidence_score', 0.5)}
problem_solving={state.get('problem_solving_score', 0.5)}

Return concise, actionable coaching.
"""
    feedback_text = _invoke_with_fallback(
        FEEDBACK_SYSTEM_PROMPT,
        prompt,
        "Coaching note: tighten the answer structure, name one concrete metric, and end with a clear decision or takeaway.",
    )
    state.setdefault("evaluation_notes", []).append(f"Feedback: {feedback_text}")
    return state


def scoring_node(state: InterviewState) -> InterviewState:
    metrics = scoring_service.score_answer(
        answer=state.get("latest_candidate_answer", ""),
        difficulty=state.get("difficulty", "medium"),
        interview_mode=state.get("interview_mode", "coaching"),
    )
    state["technical_score"] = metrics["technical_accuracy"]
    state["problem_solving_score"] = metrics["problem_solving"]
    state.setdefault("evaluation_notes", []).append(metrics["note"])
    return state


def report_node(state: InterviewState) -> InterviewState:
    state["final_report"] = scoring_service.finalize_report(state)
    return state
