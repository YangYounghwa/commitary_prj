import functools
from flask import jsonify, current_app, g

def get_db_conn():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if 'db_conn' not in g:
        # g is a special Flask object that lasts for one request.
        g.db_conn = current_app.extensions['db_pool'].getconn()
    return g.db_conn

def close_db_conn(e=None):
    """Closes the database connection at the end of the request.
    This function is now registered with app.teardown_appcontext,
    so it will be called automatically.
    """
    conn = g.pop('db_conn', None)
    if conn is not None:
        # putconn() returns the connection to the pool.
        current_app.extensions['db_pool'].putconn(conn)

def with_db_connection(func):
    """A decorator to handle database connections."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Get a connection from the pool.
            conn = get_db_conn()
            # The actual route function is called here.
            result = func(*args, conn=conn, **kwargs)
            # The connection will be closed automatically by the teardown function.
            return result
        except Exception as e:
            # If an error occurs, get the connection and roll back transactions.
            conn = g.get('db_conn', None)
            if conn:
                conn.rollback()
            
            # Log the error for debugging.
            print(f"An error occurred in a database operation: {e}")
            import traceback
            traceback.print_exc()

            # The connection will STILL be closed by the teardown function,
            # even after this exception.
            return jsonify({"error": "An internal server error occurred."}), 500
    return wrapper