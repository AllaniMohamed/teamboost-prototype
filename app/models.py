from app.database import db
from datetime import datetime
import json

class Engineer(db.Model):
    id = db.Column(db.String, primary_key=True)
    name = db.Column(db.String)
    email = db.Column(db.String)
    team = db.Column(db.String)

class Task(db.Model):
    id = db.Column(db.String, primary_key=True)
    title = db.Column(db.String)
    description = db.Column(db.Text)
    owner_id = db.Column(db.String, db.ForeignKey('engineer.id'))
    status = db.Column(db.String)
    due_date = db.Column(db.String)
    related_pr_id = db.Column(db.String, nullable=True)
    sprint_id = db.Column(db.String)
    team = db.Column(db.String)

class Dependency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String)
    depends_on_task_id = db.Column(db.String)
    type = db.Column(db.String)

class PREvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pr_id = db.Column(db.String)
    task_id = db.Column(db.String)
    status = db.Column(db.String)
    timestamp = db.Column(db.String)
    ci_message = db.Column(db.Text)

class ActivityLog(db.Model):
    id = db.Column(db.String, primary_key=True)
    task_id = db.Column(db.String)
    engineer_id = db.Column(db.String)
    type = db.Column(db.String)
    message = db.Column(db.Text)
    timestamp = db.Column(db.String)

class Investigation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pr_id = db.Column(db.String, nullable=True)
    task_id = db.Column(db.String, nullable=True)
    classification = db.Column(db.String, nullable=False)
    notification = db.Column(db.Text, nullable=False)
    tool_trace = db.Column(db.Text)                    # stored as JSON string
    status = db.Column(db.String, default="completed")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "pr_id": self.pr_id,
            "task_id": self.task_id,
            "classification": self.classification,
            "notification": self.notification,
            "tool_trace": json.loads(self.tool_trace) if self.tool_trace else [],
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }