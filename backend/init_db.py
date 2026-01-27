# init_db.py
from app.clients.database import engine
from app.models.database import Base

Base.metadata.create_all(bind=engine)
