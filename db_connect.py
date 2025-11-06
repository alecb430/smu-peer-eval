# db_connect.py
import mysql.connector
from mysql.connector import Error
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


# Provide a ready-made connection object for other modules
connection = get_connection()
