from __future__ import annotations

import statistics
from typing import Any

from app.models.schemas import ScoreCard


class ScoringService:
    filler_words = {"um", "uh", "like", "you know", "basically", "actually"}

    def estimate_confidence(self, answer: str) -> dict[str, Any]:
        lowered = answer.lower()
        filler_hits = sum(lowered.count(word) for word in self.filler_words)
        word_count = max(len(answer.split()), 1)
        avg_sentence_length = min(word_count / max(answer.count(".") + answer.count("?") + answer.count("!"), 1), 40)
        confidence = max(0.15, min(0.98, 0.82 - filler_hits * 0.06 + min(word_count / 120, 0.12)))
        clarity = max(0.2, min(0.97, 0.6 + min(avg_sentence_length / 50, 0.2) - filler_hits * 0.04))
        return {
            "confidence_score": round(confidence, 2),
            "communication_clarity": round(clarity, 2),
            "note": f"Confidence agent detected {filler_hits} filler markers across {word_count} words.",
        }

    def score_answer(self, answer: str, difficulty: str, interview_mode: str) -> dict[str, Any]:
        word_count = len(answer.split())
        base = min(0.92, 0.35 + word_count / 180)
        difficulty_bonus = {"easy": 0.0, "medium": 0.08, "hard": 0.14}.get(difficulty, 0.08)
        coaching_modifier = 0.03 if interview_mode == "coaching" else 0.0
        technical = min(0.98, base + difficulty_bonus)
        problem_solving = min(0.97, base + 0.05 + coaching_modifier)
        return {
            "technical_accuracy": round(technical, 2),
            "problem_solving": round(problem_solving, 2),
            "note": f"Scoring agent estimated depth from answer length={word_count} and difficulty={difficulty}.",
        }

    def finalize_report(self, state: dict[str, Any]) -> dict[str, Any]:
        scorecard = ScoreCard(
            technical_accuracy=round(state.get("technical_score", 0.5) * 100, 1),
            communication_clarity=round(state.get("communication_score", 0.5) * 100, 1),
            confidence_score=round(state.get("confidence_score", 0.5) * 100, 1),
            problem_solving=round(state.get("problem_solving_score", 0.5) * 100, 1),
            overall_score=round(
                statistics.mean(
                    [
                        state.get("technical_score", 0.5) * 100,
                        state.get("communication_score", 0.5) * 100,
                        state.get("confidence_score", 0.5) * 100,
                        state.get("problem_solving_score", 0.5) * 100,
                    ]
                ),
                1,
            ),
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

        return {
            "final_recommendation": recommendation,
            "scorecard": scorecard.model_dump(),
            "strengths": [
                "Strong ownership signals in answers",
                "Good adaptability across interview rounds",
                "Reasonable confidence under pressure",
            ],
            "weaknesses": [
                "Some answers can be tightened for executive-level clarity",
                "Technical examples should include clearer trade-off analysis",
                "Confidence dips when answers become long-winded",
            ],
            "improvement_roadmap": [
                "Practice 90-second STAR stories for leadership and ambiguity questions",
                "Use a repeatable framework for ML system design: latency, quality, cost, observability",
                "Reduce filler words and end answers with a crisp recommendation",
            ],
        }


scoring_service = ScoringService()

