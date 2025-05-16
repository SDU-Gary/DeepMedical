from sqlalchemy import create_engine
from src.models.session import Base
from src.database.db import DATABASE_URL

def init_db():
    """初始化数据库"""
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")