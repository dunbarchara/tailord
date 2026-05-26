from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=settings.db_pool_recycle,
    connect_args=(
        {"options": f"-c statement_timeout={settings.db_statement_timeout_ms}"}
        if settings.db_statement_timeout_ms
        else {}
    ),
)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
