from flask import Flask
from dotenv import load_dotenv
from app.database import db
from config import Config
from app.routes import api

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(api)

    db.init_app(app)

    with app.app_context():
        from app.models import Engineer
        from app.seed_loader import load_seed_data
        from app.embeddings import TaskVectorStore

        db.create_all()

        if Engineer.query.first() is None:
            load_seed_data(app)

        # Build embeddings
        app.vector_store = TaskVectorStore()
        app.vector_store.build_index()
        print("✅ FAISS index built.")

    return app