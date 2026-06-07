from app import create_app, db
from app.seed_loader import load_seed_data

app = create_app()

with app.app_context():
    db.create_all()
    load_seed_data(app)

print("Database initialized and seeded.")