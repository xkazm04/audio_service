from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv
import socket

load_dotenv()

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL")
print(f"Original DATABASE_URL: {DATABASE_URL}")

in_docker = os.getenv("CONTAINER_ENV") == "1" or os.path.exists("/.dockerenv")
print(f"Detected Docker environment: {in_docker}")

if os.getenv("TESTING") == "1" or not DATABASE_URL:
    test_db_url = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    print(f"Using test database: {test_db_url}")
else:
    if "localhost" in DATABASE_URL and in_docker:
        db_host = os.getenv("DB_HOST", "audio_db")
        DATABASE_URL = DATABASE_URL.replace("localhost", db_host)
        if ":5435" in DATABASE_URL:
            DATABASE_URL = DATABASE_URL.replace(":5435", ":5432")
            
        print(f"Modified for container: {DATABASE_URL}")
    
    try:
        if DATABASE_URL and "postgresql" in DATABASE_URL:
            parts = DATABASE_URL.replace("postgresql://", "").split("@")
            if len(parts) > 1:
                auth = parts[0]
                connection = parts[1]
                print(f"Auth: {auth}, Connection: {connection}")
                
                if ":" in connection:
                    host = connection.split(":")[0].split("/")[0]
                    port_str = connection.split(":")[1].split("/")[0]
                    port = int(port_str)
                    print(f"Testing connection to {host}:{port}")
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(2)
                        s.connect((host, port))
                        s.close()
                        print(f"Socket connection successful to {host}:{port}")
                    except Exception as e:
                        print(f"Socket connection failed: {str(e)}")
    except Exception as e:
        print(f"Error parsing URL for debug: {str(e)}")
    
    print(f"Connecting with: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()