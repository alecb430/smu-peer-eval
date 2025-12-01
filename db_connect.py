# db_connect.py
import mysql.connector
from mysql.connector import Error, OperationalError
from config import Config


def get_connection():
    """Return a ready-to-use MySQL connection to the Railway instance."""
    try:
        cn = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=False,
            connection_timeout=10,
        )
        cn.ping(reconnect=True, attempts=1, delay=0)
        return cn
    except Error as e:
        raise RuntimeError(f"Database connection failed: {e}") from e


def ensure_connection(conn=None):
    """
    Verify that a MySQL connection is active and valid.
    If the connection is None, closed, stale, or invalid, create a new one.
    Returns a fresh, validated connection.
    """
    if conn is None:
        print("DB: Connection is None, creating new connection")
        return get_connection()
    
    try:
        # Check if connection is still open
        if not conn.is_connected():
            print("DB: Connection is not connected, creating new connection")
            try:
                conn.close()
            except:
                pass
            return get_connection()
        
        # Ping the connection to verify it's alive
        conn.ping(reconnect=False, attempts=1, delay=0)
        print("DB: Connection is alive and valid")
        return conn
        
    except (OperationalError, Error) as e:
        print(f"DB: Connection check failed ({type(e).__name__}: {str(e)}), creating new connection")
        try:
            conn.close()
        except:
            pass
        return get_connection()


def get_valid_cursor(conn=None):
    """
    Get a cursor from a validated connection.
    Automatically reconnects if the connection is dead.
    Returns (cursor, connection) tuple.
    """
    valid_conn = ensure_connection(conn)
    cursor = valid_conn.cursor()
    return cursor, valid_conn


# Provide a ready-made connection object for other modules (deprecated - use ensure_connection instead)
connection = get_connection()
