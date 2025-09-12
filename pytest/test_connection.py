




import os
from dotenv import load_dotenv
import psycopg2


def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database using psycopg2.
    The connection details are fetched from environment variables.
    """
    try:
        # The connection string can be a single string from the DATABASE_URL env var
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set.")
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        print(f"Database connection success.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"Database connection failed: {e}")
        return None

load_dotenv()
get_db_connection()