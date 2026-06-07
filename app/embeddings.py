import faiss
from sentence_transformers import SentenceTransformer
from app.models import Task

class TaskVectorStore:
    def __init__(self):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.index = None
        self.task_ids = []

    def build_index(self):
        tasks = Task.query.all()

        texts = [
            f"{task.title}. {task.description}"
            for task in tasks
        ]

        embeddings = self.model.encode(texts, convert_to_numpy=True)

        dimension = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(dimension)

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)

        self.index.add(embeddings)

        self.task_ids = [task.id for task in tasks]

    def search(self, query_embedding, k=5):
        faiss.normalize_L2(query_embedding)
        scores, indices = self.index.search(query_embedding, k)
        return scores[0], indices[0]