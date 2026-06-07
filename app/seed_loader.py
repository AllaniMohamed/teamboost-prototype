import json
from app.database import db
from app.models import Engineer, Task, Dependency, PREvent, ActivityLog

def load_seed_data(app, path="seed.json"):
    with app.app_context():
        with open(path, "r") as f:
            data = json.load(f)

        # Engineers
        for eng in data["engineers"]:
            db.session.merge(Engineer(**eng))

        # Tasks
        for task in data["tasks"]:
            db.session.merge(Task(**task))

        # Dependencies
        for dep in data["dependencies"]:
            db.session.add(Dependency(**dep))

        # PR Events
        for pr in data["pr_events"]:
            db.session.add(PREvent(**pr))

        # Activity log
        for act in data["activity_log"]:
            db.session.merge(ActivityLog(**act))

        db.session.commit()