from __future__ import annotations

import statistics
from typing import Any

from app.models.schemas import ScoreCard


class ScoringService:
    filler_words = {"um", "uh", "like", "you know", "basically", "actually"}
    structure_markers = {"first", "second", "third", "because", "therefore", "tradeoff", "impact", "result"}
    technical_markers = {
        "latency",
        "throughput",
        "cache",
        "retrieval",
        "embedding",
        "monitoring",
        "observability",
        "fallback",
        "queue",
        "deployment",
        "evaluation",
        "llm",
        "api",
        "database",
    }

    def estimate_confidence(self, answer: str) -> dict[str, Any]:
        lowered = answer.lower()
        words = answer.split()
        filler_hits = sum(lowered.count(word) for word in self.filler_words)
        word_count = max(len(words), 1)
        sentence_count = max(answer.count(".") + answer.count("?") + answer.count("!"), 1)
        avg_sentence_length = min(word_count / sentence_count, 40)
        confidence = max(0.15, min(0.98, 0.8 - filler_hits * 0.06 + min(word_count / 140, 0.12)))
        clarity = max(0.2, min(0.97, 0.56 + min(avg_sentence_length / 55, 0.2) - filler_hits * 0.04))
        signal = "confident" if confidence >= 0.75 and clarity >= 0.72 else "needs_structure" if word_count < 40 else "mixed"
        return {
            "confidence_score": round(confidence, 2),
            "communication_clarity": round(clarity, 2),
            "answer_signal": signal,
            "note": f"Confidence agent detected {filler_hits} filler markers across {word_count} words.",
        }

    def score_answer(self, answer: str, difficulty: str, interview_mode: str) -> dict[str, Any]:
        lowered = answer.lower()
        words = answer.split()
        word_count = len(words)
        structure_hits = sum(1 for marker in self.structure_markers if marker in lowered)
        technical_hits = sum(1 for marker in self.technical_markers if marker in lowered)
        digit_bonus = min(sum(char.isdigit() for char in answer), 6) / 20
        word_score = min(word_count / 160, 0.35)
        difficulty_bonus = {"easy": 0.02, "medium": 0.08, "hard": 0.14}.get(difficulty, 0.08)
        coaching_modifier = 0.03 if interview_mode == "coaching" else 0.0

        technical = min(0.98, 0.34 + word_score + technical_hits * 0.035 + difficulty_bonus + digit_bonus)
        problem_solving = min(0.97, 0.33 + word_score + structure_hits * 0.04 + coaching_modifier + digit_bonus / 2)

        if word_count < 28:
            signal = "too_short"
            focus = "Add more detail, including the decision you made and its impact."
        elif technical_hits < 2:
            signal = "needs_depth"
            focus = "Add concrete system tradeoffs, metrics, or implementation details."
        elif structure_hits < 1:
            signal = "needs_structure"
            focus = "Use a clearer structure: context, action, outcome, and tradeoff."
        else:
            signal = "strong"
            focus = "Keep this same level of specificity and connect it to measurable outcomes."

        return {
            "technical_accuracy": round(technical, 2),
            "problem_solving": round(problem_solving, 2),
            "answer_signal": signal,
            "focus_recommendation": focus,
            "note": (
                f"Scoring agent saw word_count={word_count}, structure_hits={structure_hits}, "
                f"technical_hits={technical_hits}, difficulty={difficulty}."
            ),
        }

    def finalize_report(self, state: dict[str, Any]) -> dict[str, Any]:
        technical = state.get("technical_score", 0.5) * 100
        communication = state.get("communication_score", 0.5) * 100
        confidence = state.get("confidence_score", 0.5) * 100
        problem_solving = state.get("problem_solving_score", 0.5) * 100
        scorecard = ScoreCard(
            technical_accuracy=round(technical, 1),
            communication_clarity=round(communication, 1),
            confidence_score=round(confidence, 1),
            problem_solving=round(problem_solving, 1),
            overall_score=round(statistics.mean([technical, communication, confidence, problem_solving]), 1),
        )

        overall = scorecard.overall_score
        if overall >= 85:
            recommendation = "strong_hire"
        elif overall >= 75:
            recommendation = "hire"
        elif overall >= 60:
            recommendation = "mixed"
        else:
            recommendation = "no_hire"

        strengths: list[str] = []
        weaknesses: list[str] = []

        if technical >= 78:
            strengths.append("Explains technical choices with solid depth and realistic tradeoffs.")
        else:
            weaknesses.append("Technical answers need more specificity around architecture, constraints, and metrics.")

        if communication >= 76:
            strengths.append("Communicates clearly and keeps answers easy to follow.")
        else:
            weaknesses.append("Answer structure can be tighter, especially under pressure.")

        if confidence >= 74:
            strengths.append("Maintains a steady and credible interview presence.")
        else:
            weaknesses.append("Confidence drops when answers become uncertain or overly broad.")

        if problem_solving >= 78:
            strengths.append("Shows practical decision-making and good prioritization instincts.")
        else:
            weaknesses.append("Problem-solving examples should better highlight reasoning and alternatives considered.")

        if not strengths:
            strengths.append("Shows baseline readiness to discuss relevant projects and responsibilities.")
        if len(weaknesses) < 3:
            weaknesses.append("Use more outcome language: what changed, by how much, and why it mattered.")

        roadmap = [
            "Practice 60 to 90 second answers with a repeatable structure: context, action, tradeoff, result.",
            "For technical questions, name one metric, one failure mode, and one operational guardrail.",
            "Close answers with a clear takeaway instead of trailing off after implementation details.",
        ]
        if state.get("answer_signal") in {"too_short", "needs_structure"}:
            roadmap[0] = "Rehearse concise but complete stories so your answers feel structured rather than improvised."

        return {
            "final_recommendation": recommendation,
            "scorecard": scorecard.model_dump(),
            "strengths": strengths[:3],
            "weaknesses": weaknesses[:3],
            "improvement_roadmap": roadmap,
        }


scoring_service = ScoringService()
