from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from . import models
from .settings import SQLALCHEMY_DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL
)
models.Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)