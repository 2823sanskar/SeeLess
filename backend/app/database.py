from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import settings

# For SQLite, check_same_thread=False is needed for multi-threaded access in FastAPI
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db() -> None:
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if "videos" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("videos")]
            if "batch_id" not in columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE videos ADD COLUMN batch_id VARCHAR"))
                    conn.commit()
            if "workspace_id" not in columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE videos ADD COLUMN workspace_id VARCHAR"))
                    conn.commit()
    except Exception:
        pass
