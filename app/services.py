from datetime import datetime
import faiss
from app.models import Task, Dependency
from app.graph import build_graph
import networkx as nx
from flask import current_app


def get_task(task_id):
    return Task.query.filter_by(id=task_id).first()


def get_dependency_graph(task_id):
    dependencies = Dependency.query.all()
    G = build_graph(dependencies)

    upstream = nx.ancestors(G, task_id)
    downstream = nx.descendants(G, task_id)

    return {
        "upstream": list(upstream),
        "downstream": list(downstream)
    }


def get_blocked_engineers(task_id):
    dependencies = Dependency.query.all()
    G = build_graph(dependencies)

    downstream_tasks = nx.descendants(G, task_id)

    blocked = []
    for t_id in downstream_tasks:
        task = Task.query.get(t_id)
        if task and task.status == "blocked":
            blocked.append(task.owner_id)

    return blocked


def get_engineer_workload(engineer_id):
    tasks = Task.query.filter_by(owner_id=engineer_id).all()

    today = datetime.strptime("2026-06-06", "%Y-%m-%d")

    open_tasks = []
    overdue = []

    for task in tasks:
        due = datetime.strptime(task.due_date, "%Y-%m-%d")
        if task.status not in ["done", "merged"]:
            open_tasks.append(task.id)
            if due < today:
                overdue.append(task.id)

    return {
        "open_tasks": open_tasks,
        "overdue_tasks": overdue
    }

def search_related_tasks(task_id, k=5, min_score=0.75, filters=None):
    if filters is None:
        filters = {}

    task = Task.query.get(task_id)
    if not task:
        return []

    query_text = f"{task.title}. {task.description}"

    model = current_app.vector_store.model
    query_embedding = model.encode([query_text], convert_to_numpy=True)
    faiss.normalize_L2(query_embedding)
    scores, indices = current_app.vector_store.search(query_embedding, k)
    results = []

    for score, idx in zip(scores, indices):
        if idx == -1:
            continue

        if score < min_score:
            continue

        candidate_id = current_app.vector_store.task_ids[idx]

        if candidate_id == filters.get("exclude_task_id"):
            continue

        candidate = Task.query.get(candidate_id)

        # Team filter
        if "team" in filters and candidate.team != filters["team"]:
            continue

        # Status filter
        if "status" in filters and candidate.status != filters["status"]:
            continue

        results.append({
            "task_id": candidate.id,
            "score": float(score),
            "title": candidate.title
        })

    return results