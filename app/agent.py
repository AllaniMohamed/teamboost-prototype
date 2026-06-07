from dotenv import load_dotenv
load_dotenv()

from datetime import datetime
import time
from langchain_core.tools import Tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from app.services import (
    get_task,
    get_dependency_graph,
    get_blocked_engineers,
    get_engineer_workload,
    search_related_tasks
)
from app.models import PREvent, Engineer, Investigation
from app.database import db
import json
from app.queue import task_queue

def get_router_llm():
    return ChatGoogleGenerativeAI(
        model="gemma-4-31b-it",
        temperature=0
    )

def get_notification_llm():
    return ChatGoogleGenerativeAI(
        model="gemma-4-31b-it",
        temperature=0.7
    )

def extract_text_from_response(result):
    content = result.content

    # If model returns structured blocks
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        return " ".join(text_parts).strip()

    # If simple string
    return str(content).strip()

def tool_tracing_message(step: str, duration):
    return {"step": step, "duration_ms": round(duration,2), "timestamp": datetime.utcnow().isoformat()}

def build_tools():
    return [
        Tool(
            name="get_task",
            func=lambda task_id: str(get_task(task_id).__dict__),
            description="Fetch task metadata by task_id"
        ),
        Tool(
            name="get_dependency_graph",
            func=lambda task_id: str(get_dependency_graph(task_id)),
            description="Get upstream and downstream dependencies of a task"
        ),
        Tool(
            name="get_blocked_engineers",
            func=lambda task_id: str(get_blocked_engineers(task_id)),
            description="Get engineers blocked by this task"
        ),
        Tool(
            name="get_engineer_workload",
            func=lambda engineer_id: str(get_engineer_workload(engineer_id)),
            description="Get open and overdue tasks for an engineer"
        ),
        Tool(
            name="search_related_tasks",
            func=lambda task_id: str(
                search_related_tasks(
                    task_id,
                    k=5,
                    min_score=0.75,
                    filters={"exclude_task_id": task_id}
                )
            ),
            description="Search semantically related tasks using embeddings"
        ),
    ]

router_llm = get_router_llm()

router_prompt = ChatPromptTemplate.from_template("""
You are a strict classifier for engineering workflow bottlenecks.

Definitions:

DEPENDENCY_BLOCK:
Another engineer is blocked because this task has not been completed.

SELF_STALL:
The task has no downstream impact and is delayed without blocking others.

REVIEW_WAIT:
Task is waiting for review.

EXTERNAL_BLOCK:
Task blocked by non-engineering dependency.

UNKNOWN:
Cannot determine.

Given the investigation context:

{context}

Return exactly one label.
Do not explain.
""")

notification_llm = get_notification_llm()

notification_prompt = ChatPromptTemplate.from_template("""
You are an engineering productivity assistant.

Task ID: {task_id}
Task Title: {task_title}
Owner: {owner_name}
Classification: {classification}
Blocked Engineers: {blocked_engineers}

Write a clear, professional, actionable notification (2–4 sentences).

Requirements:
- Always format Task ID like: [Task ID: task-003]
- Use the engineer's real name.
- If classification is SELF_STALL, suggest providing a status update or asking for help.
- If classification is DEPENDENCY_BLOCK, mention the blocked engineers.
""")

def run_investigation(pr_id):
    from app.worker import worker_app
    with worker_app.app_context():
        return _run_investigation_internal(pr_id)

def _run_investigation_internal(pr_id):
    tool_trace = []

    # 1️⃣ Get PR event
    pr = PREvent.query.filter_by(pr_id=pr_id, status="failed").first()

    if not pr:
        return {"error": "No failed PR found"}

    task_id = pr.task_id

    start = time.time()
    # 2️⃣ Call tools manually but log them
    task = get_task(task_id)

    duration = (time.time() - start) * 1000
    tool_trace.append(tool_tracing_message("get_task",duration))
    owner = Engineer.query.get(task.owner_id)
    owner_name = owner.name if owner else task.owner_id

    duration = (time.time() - start) * 1000
    graph = get_dependency_graph(task_id)
    tool_trace.append(tool_tracing_message("get_dependency_graph", duration))

    blocked = get_blocked_engineers(task_id)
    tool_trace.append(tool_tracing_message("get_blocked_engineers",duration))
    blocked_names = []
    for eng_id in blocked:
        eng = Engineer.query.get(eng_id)
        blocked_names.append(eng.name if eng else eng_id)

    related = search_related_tasks(
        task_id,
        k=5,
        min_score=0.3,
        filters={"exclude_task_id": task_id}
    )
    duration = (time.time() - start) * 1000
    tool_trace.append(tool_tracing_message("search_related_tasks", duration))

    context = f"""
    Task: {task.title}
    Owner: {task.owner_id}
    Graph: {graph}
    Blocked engineers: {blocked}
    Related tasks: {related}
    """

    # 3️⃣ Router classification
    router_chain = router_prompt | router_llm
    result = router_chain.invoke({"context": context})
    classification = extract_text_from_response(result)
    allowed = {
        "DEPENDENCY_BLOCK",
        "SELF_STALL",
        "REVIEW_WAIT",
        "EXTERNAL_BLOCK",
        "UNKNOWN"
    }
    if classification not in allowed:
        classification = "UNKNOWN"
    duration = (time.time() - start) * 1000
    tool_trace.append(tool_tracing_message("router_llm", duration))
    # 4️⃣ Notification
    notification_chain = notification_prompt | notification_llm
    result = notification_chain.invoke({
        "classification": classification,
        "task_id": task.id,
        "task_title": task.title,
        "owner_name": owner_name,
        "blocked_engineers": blocked_names,
    })
    duration = (time.time() - start) * 1000
    tool_trace.append(tool_tracing_message("notification_llm", duration))
    notification = extract_text_from_response(result)

    investigation = Investigation(
        pr_id=pr_id,
        task_id=task_id,
        classification=classification,
        notification=notification,
        tool_trace=json.dumps(tool_trace),
        status="completed",
        created_at=datetime.utcnow()
    )

    # print(investigation.to_dict())

    db.session.add(investigation)
    db.session.commit()

    return investigation.id

def investigate(pr_id):
    job = task_queue.enqueue(run_investigation, pr_id)
    return job.id