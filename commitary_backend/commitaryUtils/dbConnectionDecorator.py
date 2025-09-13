import functools
from flask import jsonify

def with_db_connection(db_pool):
    """
    A decorator factory that creates a decorator for handling database connections.
    It passes the connection object as the first argument to the decorated function.
    
    Args:
        db_pool (psycopg2.pool.ThreadedConnectionPool): The database connection pool to use.
    """
    
    def decorator(func):
        """The actual decorator."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):

            # TODO : Delete this after Debugging Debug Line
            print(f"DEBUG: @with_db_connection decorator called for function: {func.__name__}")

            if not db_pool:
                # This should ideally be caught at startup, but it's a good fail-safe
                return jsonify({"error": "Database connection pool not available."}), 500

            conn = None
            try:
                conn = db_pool.getconn()
                # Pass the connection object to the decorated function
                result = func(conn, *args, **kwargs)
                return result
            except Exception as e:
                if conn:
                    conn.rollback()
                print(f"An error occurred in a database operation: {e}")
                return jsonify({"error": "An internal server error occurred."}), 500
            finally:
                if conn:
                    db_pool.putconn(conn)
        return wrapper
    
    return decorator
