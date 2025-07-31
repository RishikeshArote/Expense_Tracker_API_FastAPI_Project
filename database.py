from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#change this to my pc 
DATABASE_URL = "mysql+pymysql://root:rishikesh@localhost/expense_tracker_db"
# DATABASE_URL = "mysql+pymysql://root:rishikesh@host.docker.internal:3306/expense_tracker_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
