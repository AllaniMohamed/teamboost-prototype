import networkx as nx
from app.models import Task

def build_graph(dependencies):
    G = nx.DiGraph()

    # ✅ Add ALL tasks as nodes first
    tasks = Task.query.all()
    for task in tasks:
        G.add_node(task.id)

    # ✅ Then add edges
    for dep in dependencies:
        G.add_edge(dep.depends_on_task_id, dep.task_id)

    return G