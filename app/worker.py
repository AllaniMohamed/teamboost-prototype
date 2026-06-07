from app import create_app

# Build the app ONCE when worker process starts
worker_app = create_app()