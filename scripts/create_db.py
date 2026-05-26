from backend.app.db.base import Base
from backend.app.db.session import engine


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Created CineForge database tables for local development.")

