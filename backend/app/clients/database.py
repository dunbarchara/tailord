from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

DATABASE_URL = settings.database_url

# echo=True logs every SQL statement at INFO level — useful for local debugging
# but very noisy (and potentially exposes query params) in staging/production.
# TODO: condition on settings.environment == "local" once confirmed safe.
engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass
