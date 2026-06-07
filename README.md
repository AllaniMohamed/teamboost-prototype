# TeamBoostAI — Mini System-Aware PR Bottleneck Investigator
By Allani Mohamed
Hours spent: Around 24 hours
LLM Provider: Google Gemini (gemma-4-31b-it)

----

## Overview
This prototype simulates how TeamBoostAI detects workflow bottlenecks when:
- A Pull Request fails
- A task becomes blocked or overdue

The system combines:
-   ✅ Dependency graph reasoning (structural truth)
-   ✅ Semantic search using embeddings (contextual similarity)
-   ✅ Agentic workflow with router + notification LLM nodes
-   ✅ Async job processing via Redis
-   ✅ Observability logging
-   ✅ Manager-level PDF reporting

This is a hybrid AI system, not a single prompt chatbot.

----

## Core Scenario (End-to-End)

Example:
- Engineer A owns task-001
- Engineer B owns task-002 (depends on task-001)
- PR #42 fails on task-001

System:
1. Detects failure
2. Traverses dependency DAG
3. Identifies downstream blocked engineer
4. Classifies bottleneck
5. Generates actionable notification

---

## System Architecture

See  `ARCHITECTURE.md`  for full diagram.
High-level flow:
Client → Flask API → Redis Queue → RQ Worker → Agent Workflow → DB + FAISS → LLM → Persist Investigation

----
## Tech Stack

-   Flask
-   SQLite
-   SQLAlchemy
-   NetworkX (DAG)
-   SentenceTransformers (all-MiniLM-L6-v2)
-   FAISS (vector store)
-   Google Gemini (gemma-4-31b-it)
-   Redis + RQ (async processing)
-   ReportLab (PDF)
-   Pytest
---
## Setup Instructions

### 1. Clone repository
```
git clone https://github.com/AllaniMohamed/teamboost-prototype.git
cd teamboost-prototype
```

### 2. Create virtual environment
```
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Configure environment

Create  `.env`:
```
GOOGLE_API_KEY=your_key_here
```

Or copy:
```
cp .env.example .env
```
----

## Start Services

### Start Redis
```
sudo service redis-server start
```

### Start Flask API
```
flask run
```

### Start Worker (separate terminal)
```
rq worker investigations
```
----
## API Endpoints

### Health Check
```
curl http://127.0.0.1:5000/api/health
```

----------

### Trigger Investigation (Async)
```
curl -X POST http://127.0.0.1:5000/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"pr_id": "pr-042"}'
```

Returns:
```
{
  "job_id": "...",
  "status": "queued"
}
```

----------

### Check Job Status
```
curl http://127.0.0.1:5000/api/jobs/<job_id>
```

----------

### Fetch Investigation Result
```
curl http://127.0.0.1:5000/api/investigations/1
```

----------

### Dependency Graph Debug
```
curl http://127.0.0.1:5000/api/tasks/task-001/graph
```

----------

### Semantic Related Tasks
```
curl "http://127.0.0.1:5000/api/tasks/task-001/related?k=5&min_score=0.4"
```

----------

### Download Manager PDF Report
```
curl -o report.pdf http://127.0.0.1:5000/api/report/pdf
```

----

## Embeddings & Retrieval

### Embedding Model

-   Model:  `all-MiniLM-L6-v2`
-   Dimension: 384

### What Is Embedded?

Each task:
```
task.title + task.description
```

Reason:  
Tasks are short documents; chunking unnecessary.

### Vector Store

-   FAISS IndexFlatIP
-   L2-normalized embeddings
-   Cosine similarity via inner product

### Retrieval Parameters

-   top-k: 5
-   threshold: 0.4 (empirically tuned)
-   metadata filters:
    -   exclude_task_id
    -   team
    -   status

If no results pass threshold → empty list returned.

### Rebuilding Index

Index builds automatically on startup.

Manual rebuild:
```
python scripts/rebuild_index.py
```

----

## Agentic Workflow

The agent follows:

1.  get_task
2.  get_dependency_graph
3.  get_blocked_engineers
4.  search_related_tasks
5.  Router classification (LLM, temp=0)
6.  Notification generation (LLM, temp=0.7)

### Router Configuration

-   temperature = 0
-   deterministic classification
-   strict label enforcement

### Notification Configuration

-   temperature = 0.7
-   natural language generation

----

## Async Job Queue (Stretch Goal)

`POST /api/investigate`  returns immediately.

Reason:

-   LLM calls are slow (2–5 seconds)
-   Prevents blocking HTTP request
-   Enables scaling workers independently

Redis queue decouples:

API layer → AI processing

---

## Observability (Stretch Goal)

Each investigation logs:

-   Tool name
-   Duration (ms)
-   Timestamp
-   LLM latency

Stored in  `tool_trace`.

Enables performance debugging and future monitoring integration.

----

## PDF Report (Stretch Goal)

Manager report includes:

-   Executive summary
-   Classification breakdown
-   PR failures
-   Downstream impact
-   Semantic related tasks
-   AI recommendations

Generated dynamically from Task + PR + Dependency data.

Investigations included as appendix.

---

## Seed Data

Located in  `seed.json`.

Includes:

-   Engineers
-   Tasks
-   Dependencies
-   PR events
-   Activity logs

Core dependency-stall scenario:

task-002 depends on task-001  
pr-042 fails → engineer-b blocked by engineer-a

---

## Tests

Run:
```
pytest
```

Includes:

-   ≥2 graph tests
-   ≥1 embedding test
-   Agent logic test
-   API integration test

---
## Scalability Notes

For production:

-   Replace SQLite with PostgreSQL
-   Replace FAISS with pgvector
-   Add Redis cluster
-   Add monitoring (Prometheus)

---

## Future Work

-   SLA severity scoring
-   Notification delivery simulation
-   Dashboard UI
-   Full Graph RAG with Neo4j
-   Metrics endpoint

---