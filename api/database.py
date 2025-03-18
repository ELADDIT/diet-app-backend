import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load DATABASE_URL from environment variable (or use a default)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://my_user:my_password@db:5432/my_database")

# Create a database engine
engine = create_engine(DATABASE_URL)

# Create a configured Session class
SessionLocal = sessionmaker(bind=engine)
