import functools
from flask import jsonify


import functools
from flask import jsonify
# ADD THIS IMPORT
from commitary_backend.database import db_pool

# CHANGE THE FUNCTION SIGNATURE
def with_db_connection(func):
    """
    A decorator for handling database connections.
    It retrieves the pool at runtime and passes the connection object 
    as the first argument to the decorated function.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):

        print(f"DEBUG: @with_db_connection decorator called for function: {func.__name__}")

        if not db_pool:
            print("DEBUG: db_pool is not available.")
            return jsonify({"error": "Database connection pool not available."}), 500

        conn = None
        try:
            print("DEBUG: Attempting to get connection from db_pool.")
            conn = db_pool.getconn()
            print("DEBUG: Successfully got connection from db_pool.")
            # Pass the connection object to the decorated function
            result = func(conn, *args, **kwargs)
            return result
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"An error occurred in a database operation: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": "An internal server error occurred."}), 500
        finally:
            if conn:
                print("DEBUG: Returning connection to db_pool.")
                db_pool.putconn(conn)
    return wrapper