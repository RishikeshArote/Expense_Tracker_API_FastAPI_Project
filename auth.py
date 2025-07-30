from fastapi import Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import SessionLocal
import crud
import models

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def login_user(request: Request, db: Session, email: str = Form(...), password: str = Form(...)):
    user = crud.authenticate_user(db, email, password)
    if not user:
        return None
    request.session["user_id"] = user.id
    return user

def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id:
        return db.query(models.User).filter(models.User.id == user_id).first()
    return None
