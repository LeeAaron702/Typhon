from database import Base
from sqlalchemy import Column, Integer, String

class Users(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    hashed_password = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True)
    stripe_customer_id = Column(String, unique=True)
    ai_api_counter = Column(Integer, default=0)