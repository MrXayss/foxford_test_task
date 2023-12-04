from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Tickets(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    applicant_name = Column(String)
    applicant_id = Column(Integer)
    text_ticket = Column(String)
    status = Column(String, default='Открыт')
    employee = Column(String, nullable=True)
    date_create = Column(DateTime)
    date_update = Column(DateTime, nullable=True)
    message_send = Column(String, nullable=True)
    message_answer = Column(String, nullable=True)

