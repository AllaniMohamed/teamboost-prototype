from app import create_app
from app.embeddings import TaskVectorStore

app = create_app()

with app.app_context():
    store = TaskVectorStore()
    store.build_index()
    print("✅ Embedding index rebuilt successfully.")