from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

DATABASE_URL = settings.database_url

# echo=True logs every SQL statement at INFO level — useful for local debugging
# but very noisy (and potentially exposes query params) in staging/production.
engine = create_engine(DATABASE_URL, echo=settings.environment == "local")

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
