from __future__ import annotations

import json
from typing import Any

from app.agents.prompts import (
    FEEDBACK_SYSTEM_PROMPT,
    HIRING_MANAGER_SYSTEM_PROMPT,
    HR_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    TECHNICAL_SYSTEM_PROMPT,
)
from app.agents.state import InterviewState
from app.core.config import settings
from app.services.hf_service import hf_service
from app.services.scoring_service import scoring_service


def _invoke_with_fallback(system_prompt: str, prompt: str, fallback_text: str) -> str:
    if not hf_service.is_enabled():
        return fallback_text
    try:
        response = hf_service.client.chat_completion(
            model=settings.hf_chat_model or None,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.35,
            max_tokens=300,
        )
        return response.choices[0].message.content or fallback_text
    except Exception:
        return fallback_text


def _history_as_text(history: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{item.get('speaker', 'unknown')}::{item.get('agent', 'candidate')} -> {item.get('text', '')}"
        for item in history[-10:]
    )


def _resume_highlights(state: InterviewState) -> list[str]:
    return [item for item in state.get("resume_highlights", []) if item]


def _resume_reference(state: InterviewState, index: int = 0) -> str:
    highlights = _resume_highlights(state)
    if highlights:
        return highlights[index % len(highlights)]
    summary = state.get("resume_summary", "").strip()
    return summary or "the experience highlighted in your resume"


def _resume_question(state: InterviewState, stage: str) -> str:
    primary = _resume_reference(state, 0)
    secondary = _resume_reference(state, 1)
    signal = state.get("answer_signal", "mixed")

    if stage == "hr":
        if signal in {"too_short", "needs_structure"}:
            return (
                f"You mentioned {primary}. Could you walk me through it a bit more clearly, "
                "especially what you owned directly and what changed because of your work?"
            )
        return (
            f"I was looking at {primary} on your resume. What made that experience especially relevant to the {state.get('role')} role, "
            "and what part of it did you personally own?"
        )

    if stage == "technical":
        if signal in {"too_short", "needs_depth"}:
            return (
                f"Let's stay on {primary} for a second. What architecture or implementation choices mattered most there, "
                "and what tradeoffs did you have to make?"
            )
        return (
            f"{primary} stood out to me on your resume. If you were walking me through the system behind that work, "
            "how would you explain the design, the main constraints, and how you knew it was working?"
        )

    return (
        f"When you look across {primary} and {secondary}, which one best shows how you think about impact and priorities, "
        "and how would that shape your first 90 days here?"
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
    if not hf_service.is_enabled():
        turn_count = state.get("turn_count", 0)
        answer_signal = state.get("answer_signal", "mixed")
        technical_score = state.get("technical_score", 0.5)
        active_agent = "hr" if turn_count <= 1 else "technical" if turn_count <= 4 else "hiring_manager"
        if answer_signal in {"too_short", "needs_depth", "needs_structure"} and turn_count < settings.max_turns_per_session - 1:
            next_action = "ask_follow_up"
        elif active_agent == "technical" and technical_score > 0.78:
            next_action = "increase_difficulty"
        else:
            next_action = "switch_round"
        decision = {
            "active_agent": active_agent,
            "next_action": next_action,
            "difficulty": "hard" if technical_score > 0.8 else "medium" if technical_score > 0.58 else "easy",
            "should_end": turn_count >= settings.max_turns_per_session,
            "rationale": f"Fallback planner selected {active_agent} with signal={answer_signal} and technical_score={technical_score:.2f}.",
        }
    else:
        try:
            response = hf_service.client.chat_completion(
                model=settings.hf_chat_model or None,
                messages=[
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": planner_prompt},
                ],
                temperature=0.2,
                max_tokens=250,
            )
            planner_content = response.choices[0].message.content or ""
            decision = json.loads(planner_content)
        except Exception:
            turn_count = state.get("turn_count", 0)
            decision = {
                "active_agent": "hr" if turn_count <= 1 else "technical" if turn_count <= 3 else "hiring_manager",
                "next_action": "ask_follow_up",
                "difficulty": "hard" if state.get("technical_score", 0.5) > 0.75 else "medium",
                "should_end": turn_count >= settings.max_turns_per_session,
                "rationale": "Fallback planner selected a deterministic interview progression because Hugging Face planning was unavailable.",
            }

    state["active_agent"] = decision.get("active_agent", "technical")
    state["next_action"] = decision.get("next_action", "ask_follow_up")
    state["difficulty"] = decision.get("difficulty", state.get("difficulty", "medium"))
    state["should_end"] = bool(decision.get("should_end", False)) or (
        state.get("turn_count", 0) >= settings.max_turns_per_session
    )
    state["planner_rationale"] = decision.get("rationale", "")
    state.setdefault("evaluation_notes", []).append(f"Planner: {decision.get('rationale', '')}")
    return state


def confidence_node(state: InterviewState) -> InterviewState:
    metrics = scoring_service.estimate_confidence(state.get("latest_candidate_answer", ""))
    state["confidence_score"] = metrics["confidence_score"]
    state["communication_score"] = metrics["communication_clarity"]
    state["answer_signal"] = metrics["answer_signal"]
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
Make it sound like a live interviewer who listened carefully.
Current signal: {state.get('answer_signal', 'mixed')}
Coach toward: {state.get('focus_recommendation', '')}
"""
    state["last_agent_response"] = _invoke_with_fallback(
        HR_SYSTEM_PROMPT,
        prompt,
        _resume_question(state, "hr"),
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
Keep it conversational and avoid sounding like a generated quiz.
If the answer signal is weak, ask a pointed follow-up on missing tradeoffs or metrics before changing topics.
Current signal: {state.get('answer_signal', 'mixed')}
Coach toward: {state.get('focus_recommendation', '')}
"""
    state["last_agent_response"] = _invoke_with_fallback(
        TECHNICAL_SYSTEM_PROMPT,
        prompt,
        _resume_question(state, "technical"),
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
Keep the tone calm and executive-friendly.
Reference gaps or strengths that have already appeared.
"""
    state["last_agent_response"] = _invoke_with_fallback(
        HIRING_MANAGER_SYSTEM_PROMPT,
        prompt,
        _resume_question(state, "hiring_manager"),
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
        "Quick coaching note: tighten the structure, give one concrete metric, and land on a clear takeaway.",
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
    state["answer_signal"] = metrics["answer_signal"]
    state["focus_recommendation"] = metrics["focus_recommendation"]
    state.setdefault("evaluation_notes", []).append(metrics["note"])
    return state


def report_node(state: InterviewState) -> InterviewState:
    state["final_report"] = scoring_service.finalize_report(state)
    return state
