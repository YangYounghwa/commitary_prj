import os
from urllib.parse import urlparse
from psycopg2 import pool
from dotenv import load_dotenv
load_dotenv()

def create_db_pool(app):
    """Creates the database pool and attaches it to the Flask app object."""
    # Prevent creating the pool if it already exists on the app
    if 'db_pool' in app.extensions:
        return

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    
    try:
        url = urlparse(db_url)
        db_pool = pool.ThreadedConnectionPool(
            minconn=1, maxconn=100,
            user=url.username, password=url.password,
            host=url.hostname, port=url.port,
            dbname=url.path[1:]
        )
        # Attach the pool to the app using the standard extensions pattern
        app.extensions['db_pool'] = db_pool
        print("Database connection pool created successfully.")
    except Exception as e:
        raise RuntimeError(f"Failed to create database connection pool: {e}")