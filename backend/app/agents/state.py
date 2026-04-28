from __future__ import annotations

from typing import Any, Literal, TypedDict


class InterviewState(TypedDict, total=False):
    session_id: str
    candidate_id: str
    role: str
    interview_mode: Literal["strict", "coaching"]
    domain_focus: list[str]
    turn_count: int
    active_agent: str
    next_action: str
    difficulty: Literal["easy", "medium", "hard"]
    conversation_history: list[dict[str, Any]]
    latest_candidate_answer: str
    resume_context: str
    resume_summary: str
    resume_highlights: list[str]
    evaluation_notes: list[str]
    confidence_score: float
    communication_score: float
    technical_score: float
    problem_solving_score: float
    should_end: bool
    current_prompt: str
    last_agent_response: str
    final_report: dict[str, Any]
    answer_signal: str
    focus_recommendation: str
    planner_rationale: str
