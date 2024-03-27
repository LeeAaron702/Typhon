# fastapi\utilities\increment_ai_api_counter.py
from database import get_db
from models import Users
from sqlalchemy.orm import Session

def increment_ai_api_counter(user_id: int, db_session: Session):
    # Retrieve the user's record
    user = db_session.query(Users).filter(Users.id == user_id).first()
    if user:
        # Increment the counter and save the change
        user.ai_api_counter += 1
        db_session.commit()
