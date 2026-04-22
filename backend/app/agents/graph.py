from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    confidence_node,
    feedback_node,
    hiring_manager_node,
    hr_node,
    planner_node,
    report_node,
    scoring_node,
    technical_node,
)
from app.agents.state import InterviewState


def _route_active_agent(state: InterviewState) -> str:
    if state.get("should_end"):
        return "report"
    return state.get("active_agent", "technical")


def _route_feedback(state: InterviewState) -> str:
    if state.get("interview_mode") == "coaching":
        return "feedback"
    return END


def build_interview_graph():
    graph = StateGraph(InterviewState)
    graph.add_node("planner", planner_node)
    graph.add_node("confidence", confidence_node)
    graph.add_node("scoring", scoring_node)
    graph.add_node("hr", hr_node)
    graph.add_node("technical", technical_node)
    graph.add_node("hiring_manager", hiring_manager_node)
    graph.add_node("feedback", feedback_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "confidence")
    graph.add_edge("confidence", "scoring")
    graph.add_edge("scoring", "planner")
    graph.add_conditional_edges(
        "planner",
        _route_active_agent,
        {
            "hr": "hr",
            "technical": "technical",
            "hiring_manager": "hiring_manager",
            "report": "report",
        },
    )
    graph.add_conditional_edges("hr", _route_feedback, {"feedback": "feedback", END: END})
    graph.add_conditional_edges("technical", _route_feedback, {"feedback": "feedback", END: END})
    graph.add_conditional_edges("hiring_manager", _route_feedback, {"feedback": "feedback", END: END})
    graph.add_edge("feedback", END)
    graph.add_edge("report", END)
    return graph.compile()


interview_graph = build_interview_graph()

