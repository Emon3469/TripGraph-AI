import json
import logging
import operator
import re
import time
from datetime import date
from functools import wraps
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from app import prompts
from app.llm import AllProvidersFailed, get_router
from app.tools.mcp_client import weather_report, web_search

logger = logging.getLogger("tripgraph.graph")

RESEARCH_AGENTS = ["flight_agent", "hotel_agent", "weather_agent"]
ALL_AGENTS = [*RESEARCH_AGENTS, "budget_agent"]


class TravelState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    user_input: str
    mode: str
    guardrail_allowed: bool
    guardrail_reason: str
    selected_agents: list[str]
    trip_constraints: dict[str, Any]
    supervisor_reasoning: str
    flight_results: str
    hotel_results: str
    weather_results: str
    budget_results: str
    itinerary: str
    approval_request: str
    approved: bool
    human_feedback: str
    revision_count: int
    final_response: str
    llm_calls: Annotated[int, operator.add]


def new_turn(user_input: str) -> TravelState:
    return {
        "messages": [HumanMessage(content=user_input)],
        "user_input": user_input,
        "mode": "plan",
        "guardrail_allowed": True,
        "guardrail_reason": "",
        "selected_agents": [],
        "trip_constraints": {},
        "supervisor_reasoning": "",
        "flight_results": "",
        "hotel_results": "",
        "weather_results": "",
        "budget_results": "",
        "itinerary": "",
        "approval_request": "",
        "approved": False,
        "human_feedback": "",
        "revision_count": 0,
        "final_response": "",
        "llm_calls": 0,
    }


def _today() -> str:
    return date.today().strftime("%A, %d %B %Y")


def _emit(event: dict[str, Any]) -> None:
    try:
        get_stream_writer()(event)
    except Exception:
        pass


def _history(state: TravelState, limit: int = 6) -> str:
    messages = state.get("messages", [])[:-1][-limit:]
    lines = []
    for message in messages:
        role = "User" if isinstance(message, HumanMessage) else "Assistant"
        content = str(message.content).strip().replace("\n", " ")
        lines.append(f"{role}: {content[:600]}")
    return "\n".join(lines) or "(no earlier messages)"


def _constraints(state: TravelState) -> dict[str, Any]:
    return state.get("trip_constraints") or {}


def _constraints_text(state: TravelState) -> str:
    data = {k: v for k, v in _constraints(state).items() if v not in (None, "", [], {})}
    return json.dumps(data, ensure_ascii=False) if data else "none given"


def _note(state: TravelState, key: str, limit: int = 1400) -> str:
    text = (state.get(key) or "").strip()
    if not text:
        return "not researched"
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def _parse_json(text: str) -> dict[str, Any]:
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


def tracked(name: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(state: TravelState):
            started = time.perf_counter()
            _emit({"type": "agent", "agent": name, "status": "running"})
            try:
                result = await func(state)
            except Exception:
                _emit({"type": "agent", "agent": name, "status": "failed"})
                raise
            _emit(
                {
                    "type": "agent",
                    "agent": name,
                    "status": "done",
                    "ms": round((time.perf_counter() - started) * 1000),
                }
            )
            return result

        return wrapper

    return decorator


async def _complete(system: str, prompt: str, tier: str = "fast") -> str:
    text, _ = await get_router().ainvoke(
        [SystemMessage(content=system), HumanMessage(content=prompt)], tier=tier
    )
    return text


async def _summarise(fallback: str, system: str, prompt: str) -> tuple[str, int]:
    try:
        return await _complete(system, prompt), 1
    except AllProvidersFailed as error:
        logger.warning("Specialist summary unavailable, passing research through: %s", str(error)[:200])
        return fallback, 0


async def _stream(node: str, system: str, prompt: str) -> str:
    parts: list[str] = []
    async for kind, value in get_router().astream(
        [SystemMessage(content=system), HumanMessage(content=prompt)], tier="smart"
    ):
        if kind == "token":
            parts.append(value)
            _emit({"type": "token", "node": node, "content": value})
        elif kind == "reset":
            parts.clear()
            _emit({"type": "reset", "node": node})
        elif kind == "provider":
            _emit({"type": "provider", "node": node, "provider": value})
        elif kind == "waiting":
            _emit({"type": "status", "message": "High demand on the AI models - retrying in a few seconds."})
    return "".join(parts).strip()


@tracked("supervisor")
async def supervisor_agent(state: TravelState):
    query = state["user_input"]
    try:
        raw = await _complete(
            prompts.SUPERVISOR_SYSTEM.format(today=_today()),
            prompts.SUPERVISOR_PROMPT.format(history=_history(state), query=query),
        )
        parsed = _parse_json(raw)
    except Exception as error:
        logger.warning("Supervisor fell back to the full workflow: %s", error)
        parsed = {
            "allowed": True,
            "mode": "plan",
            "selected_agents": ALL_AGENTS,
            "trip_constraints": {},
            "reasoning": "Routing fallback: running every specialist.",
        }

    allowed = bool(parsed.get("allowed", True))
    mode = "plan" if parsed.get("mode") == "plan" else "answer"
    requested = parsed.get("selected_agents") or []
    selected = [agent for agent in ALL_AGENTS if agent in requested]
    constraints = parsed.get("trip_constraints") if isinstance(parsed.get("trip_constraints"), dict) else {}
    if not constraints.get("destination") and constraints.get("weather_city"):
        constraints["destination"] = constraints["weather_city"]
    if not constraints.get("destination"):
        selected = [agent for agent in selected if agent not in RESEARCH_AGENTS]

    update: TravelState = {
        "guardrail_allowed": allowed,
        "guardrail_reason": "" if allowed else str(parsed.get("reason") or prompts.BLOCKED_MESSAGE),
        "mode": mode,
        "selected_agents": selected if allowed else [],
        "trip_constraints": constraints,
        "supervisor_reasoning": str(parsed.get("reasoning", "")),
        "llm_calls": 1,
    }
    _emit(
        {
            "type": "plan",
            "allowed": allowed,
            "mode": mode,
            "selected_agents": update["selected_agents"],
            "trip_constraints": constraints,
            "reasoning": update["supervisor_reasoning"],
        }
    )
    return update


@tracked("guardrail_blocked")
async def guardrail_blocked_agent(state: TravelState):
    message = prompts.BLOCKED_MESSAGE
    _emit({"type": "token", "node": "guardrail_blocked", "content": message})
    return {"final_response": message, "messages": [AIMessage(content=message)]}


@tracked("flight_agent")
async def flight_agent(state: TravelState):
    c = _constraints(state)
    destination = c.get("destination", "")
    origin = c.get("origin", "")
    query = (
        f"flights from {origin} to {destination} airlines duration fare"
        if origin
        else f"flights to {destination} main international airport airlines"
    )
    try:
        search = await web_search(query, max_results=4)
    except Exception as error:
        logger.warning("Flight search failed: %s", error)
        search = "No live results available."
    text, calls = await _summarise(
        f"Live flight search notes:\n{search or 'none'}",
        prompts.FLIGHT_SYSTEM,
        prompts.FLIGHT_PROMPT.format(
            query=state["user_input"],
            origin=origin or "not specified",
            destination=destination,
            dates=c.get("dates") or "not specified",
            search=search or "No live results available.",
        ),
    )
    return {"flight_results": text, "llm_calls": calls}


@tracked("hotel_agent")
async def hotel_agent(state: TravelState):
    c = _constraints(state)
    destination = c.get("destination", "")
    style = c.get("travel_style") or ""
    try:
        search = await web_search(f"best {style} hotels in {destination} where to stay".strip(), max_results=5)
    except Exception as error:
        logger.warning("Hotel search failed: %s", error)
        search = "No live results available."
    text, calls = await _summarise(
        f"Live hotel search notes:\n{search or 'none'}",
        prompts.HOTEL_SYSTEM,
        prompts.HOTEL_PROMPT.format(
            query=state["user_input"],
            destination=destination,
            budget=c.get("budget") or "not specified",
            style=style or "not specified",
            search=search or "No live results available.",
        ),
    )
    return {"hotel_results": text, "llm_calls": calls}


@tracked("weather_agent")
async def weather_agent(state: TravelState):
    c = _constraints(state)
    city = c.get("weather_city") or c.get("destination") or ""
    try:
        report = await weather_report(city)
        text = f"Current conditions in {city}: {report['current']}\nForecast: {report['forecast']}"
    except Exception as error:
        logger.warning("Weather lookup failed for %s: %s", city, error)
        text = (
            f"Live weather for {city} is unavailable right now. Use typical seasonal climate for the "
            "travel dates and advise checking the forecast before departure."
        )
    return {"weather_results": text}


async def research_join(state: TravelState):
    return {}


@tracked("budget_agent")
async def budget_agent(state: TravelState):
    text, calls = await _summarise(
        "Detailed budget analysis is unavailable; estimate costs from the flight and hotel notes.",
        prompts.BUDGET_SYSTEM,
        prompts.BUDGET_PROMPT.format(
            query=state["user_input"],
            constraints=_constraints_text(state),
            flights=_note(state, "flight_results"),
            hotels=_note(state, "hotel_results"),
        ),
    )
    return {"budget_results": text, "llm_calls": calls}


@tracked("itinerary_agent")
async def itinerary_agent(state: TravelState):
    revision = ""
    if state.get("human_feedback") and state.get("itinerary"):
        revision = prompts.REVISION_BLOCK.format(
            feedback=state["human_feedback"], draft=state["itinerary"]
        )
    draft = await _stream(
        "itinerary_agent",
        prompts.ITINERARY_SYSTEM.format(today=_today()),
        prompts.ITINERARY_PROMPT.format(
            query=state["user_input"],
            constraints=_constraints_text(state),
            flights=_note(state, "flight_results"),
            hotels=_note(state, "hotel_results"),
            weather=_note(state, "weather_results"),
            budget=_note(state, "budget_results"),
            revision=revision,
        ),
    )
    return {
        "itinerary": draft,
        "approval_request": "Review the draft itinerary. Approve it to generate the final plan, or describe the changes you want.",
        "human_feedback": "",
        "llm_calls": 1,
    }


async def human_approval(state: TravelState):
    review = interrupt(
        {
            "question": "Do you approve this itinerary?",
            "draft_itinerary": state.get("itinerary", ""),
            "approval_request": state.get("approval_request", ""),
            "selected_agents": state.get("selected_agents", []),
        }
    )
    review = review if isinstance(review, dict) else {"approved": bool(review)}
    approved = bool(review.get("approved"))
    feedback = str(review.get("feedback") or "").strip()
    return {
        "approved": approved,
        "human_feedback": feedback,
        "revision_count": state.get("revision_count", 0) + (0 if approved else 1),
    }


@tracked("final_agent")
async def final_agent(state: TravelState):
    if state.get("mode") == "plan":
        system = prompts.FINAL_PLAN_SYSTEM.format(today=_today())
        prompt = prompts.FINAL_PLAN_PROMPT.format(
            query=state["user_input"],
            constraints=_constraints_text(state),
            draft=state.get("itinerary", ""),
            flights=_note(state, "flight_results"),
            hotels=_note(state, "hotel_results"),
            weather=_note(state, "weather_results"),
            budget=_note(state, "budget_results"),
        )
    else:
        notes = "\n\n".join(
            f"{label}:\n{state[key]}"
            for label, key in (
                ("Flights", "flight_results"),
                ("Hotels", "hotel_results"),
                ("Weather", "weather_results"),
                ("Budget", "budget_results"),
            )
            if state.get(key)
        )
        system = prompts.ANSWER_SYSTEM.format(today=_today())
        prompt = prompts.ANSWER_PROMPT.format(
            history=_history(state), query=state["user_input"], notes=notes or "none"
        )

    answer = await _stream("final_agent", system, prompt)
    return {"final_response": answer, "messages": [AIMessage(content=answer)], "llm_calls": 1}


def route_from_supervisor(state: TravelState) -> str | list[str]:
    if not state.get("guardrail_allowed", True):
        return "guardrail_blocked"
    research = [agent for agent in RESEARCH_AGENTS if agent in state.get("selected_agents", [])]
    return research or route_after_research(state)


def route_after_research(state: TravelState) -> str:
    if "budget_agent" in state.get("selected_agents", []):
        return "budget_agent"
    return route_after_budget(state)


def route_after_budget(state: TravelState) -> str:
    return "itinerary_agent" if state.get("mode") == "plan" else "final_agent"


def route_after_review(state: TravelState) -> str:
    if state.get("approved") or state.get("revision_count", 0) > 5:
        return "final_agent"
    return "itinerary_agent"


def build_graph() -> StateGraph:
    graph = StateGraph(TravelState)
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("guardrail_blocked", guardrail_blocked_agent)
    graph.add_node("flight_agent", flight_agent)
    graph.add_node("hotel_agent", hotel_agent)
    graph.add_node("weather_agent", weather_agent)
    graph.add_node("research_join", research_join)
    graph.add_node("budget_agent", budget_agent)
    graph.add_node("itinerary_agent", itinerary_agent)
    graph.add_node("human_approval", human_approval)
    graph.add_node("final_agent", final_agent)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        ["guardrail_blocked", *RESEARCH_AGENTS, "budget_agent", "itinerary_agent", "final_agent"],
    )
    for agent in RESEARCH_AGENTS:
        graph.add_edge(agent, "research_join")
    graph.add_conditional_edges(
        "research_join", route_after_research, ["budget_agent", "itinerary_agent", "final_agent"]
    )
    graph.add_conditional_edges("budget_agent", route_after_budget, ["itinerary_agent", "final_agent"])
    graph.add_edge("itinerary_agent", "human_approval")
    graph.add_conditional_edges("human_approval", route_after_review, ["final_agent", "itinerary_agent"])
    graph.add_edge("final_agent", END)
    graph.add_edge("guardrail_blocked", END)
    return graph
