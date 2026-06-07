from flask import Blueprint, request, jsonify, send_file
from app.agent import investigate
from app.services import get_dependency_graph, search_related_tasks
from app.models import Investigation
from app.reporting import generate_manager_report
from rq.job import Job
from app.queue import redis_conn

api = Blueprint("api", __name__)

@api.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@api.route("/api/investigate", methods=["POST"])
def start_investigation():
    data = request.json
    pr_id = data.get("pr_id")

    if not pr_id:
        return jsonify({"error": "Provide pr_id"}), 400

    job_id = investigate(pr_id)

    return jsonify({
        "job_id": job_id,
        "status": "queued"
    })

@api.route("/api/investigations/<int:investigation_id>", methods=["GET"])
def get_investigation(investigation_id):
    investigation = Investigation.query.get(investigation_id)

    if not investigation:
        return jsonify({"error": "Not found"}), 404

    return jsonify(investigation.to_dict())

@api.route("/api/tasks/<task_id>/graph", methods=["GET"])
def task_graph(task_id):
    result = get_dependency_graph(task_id)
    return jsonify(result)

@api.route("/api/tasks/<task_id>/related", methods=["GET"])
def related_tasks(task_id):
    k = int(request.args.get("k", 5))
    min_score = float(request.args.get("min_score", 0.5))

    results = search_related_tasks(
        task_id,
        k=k,
        min_score=min_score,
        filters={"exclude_task_id": task_id}
    )

    return jsonify({
        "task_id": task_id,
        "k": k,
        "min_score": min_score,
        "results": results
    })

@api.route("/api/report/pdf", methods=["GET"])
def download_pdf():
    pdf_buffer = generate_manager_report()

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name="teamboost_report.pdf",
        mimetype="application/pdf"
    )

@api.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    job = Job.fetch(job_id, connection=redis_conn)

    return jsonify({
        "job_id": job.id,
        "status": job.get_status(),
        "result": job.result
    })