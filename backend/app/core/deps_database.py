from app.clients.database import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()  # no-op if already committed; ensures no dirty connection returns to pool
        db.close()
