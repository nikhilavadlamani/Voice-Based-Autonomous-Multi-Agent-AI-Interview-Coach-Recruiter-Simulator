from typing import Any, Literal

from pydantic import BaseModel, Field


class ResumeUploadResponse(BaseModel):
    candidate_id: str
    filename: str
    chunks_indexed: int
    extracted_summary: str
    resume_highlights: list[str] = Field(default_factory=list)


class SessionCreateRequest(BaseModel):
    candidate_id: str
    role: str = "Machine Learning Engineer"
    interview_mode: Literal["strict", "coaching"] = "coaching"
    domain_focus: list[str] = Field(default_factory=lambda: ["ml", "system-design", "coding"])


class SessionCreateResponse(BaseModel):
    session_id: str
    greeting: str
    first_speaker: str


class SessionSummary(BaseModel):
    session_id: str
    role: str
    interview_mode: Literal["strict", "coaching"]
    turn_count: int
    active_agent: str
    difficulty: str
    status: Literal["ready", "live", "completed", "closed"]
    latest_signal: str
    focus_recommendation: str


class TranscriptTurn(BaseModel):
    speaker: Literal["candidate", "agent"]
    agent: str | None = None
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoreCard(BaseModel):
    technical_accuracy: float
    communication_clarity: float
    confidence_score: float
    problem_solving: float
    overall_score: float


class SessionReport(BaseModel):
    session_id: str
    final_recommendation: Literal["strong_hire", "hire", "mixed", "no_hire"]
    scorecard: ScoreCard
    strengths: list[str]
    weaknesses: list[str]
    improvement_roadmap: list[str]
    transcript: list[TranscriptTurn]
