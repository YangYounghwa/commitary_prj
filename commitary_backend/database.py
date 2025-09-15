import os
from urllib.parse import urlparse
from psycopg2 import pool
from dotenv import load_dotenv
load_dotenv()

db_pool = None

def create_db_pool():
    global db_pool
    if db_pool:
        return
    db_url = os.getenv("DATABASE_URL")
    # print("DEBUG : " + db_url)
    if not db_url:
        print("DATABASE_URL environment variable is not set.")
        return
    try:
        url = urlparse(db_url)
        db_pool = pool.ThreadedConnectionPool(
            minconn=1, maxconn=20,
            user=url.username, password=url.password,
            host=url.hostname, port=url.port,
            dbname=url.path[1:]
        )
        print("Database connection pool created successfully.")
    except Exception as e:
        print(f"Failed to create database connection pool: {e}")
        db_pool = None