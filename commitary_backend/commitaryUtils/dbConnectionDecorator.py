import functools
from flask import jsonify



import functools
from flask import jsonify, current_app, g

def get_db_conn():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if 'db_conn' not in g:
        g.db_conn = current_app.extensions['db_pool'].getconn()
    return g.db_conn

def close_db_conn(e=None):
    """Closes the database connection at the end of the request."""
    conn = g.pop('db_conn', None)
    if conn is not None:
        current_app.extensions['db_pool'].putconn(conn)

def with_db_connection(func):
    """A decorator to handle database connections."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            conn = get_db_conn()
            result = func(*args, conn=conn, **kwargs)

            return result
        except Exception as e:
            # Rollback in case of error
            conn = g.get('db_conn', None)
            if conn:
                conn.rollback()
            print(f"An error occurred in a database operation: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": "An internal server error occurred."}), 500
    return wrapper
