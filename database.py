import os
import psycopg2
import hashlib
import uuid
from datetime import datetime
from dotenv import load_dotenv

class Database:
    def __init__(self):
        load_dotenv()
        self.database_url = os.getenv("DATABASE_URL")  # Change to your DB URL
        self.conn = None
        self.connect_db()

    def connect_db(self):
        """Establish a new connection if it is closed or None."""
        try:
            if self.conn is None or self.conn.closed:
                self.conn = psycopg2.connect(self.database_url, sslmode="require")
                self.conn.autocommit = True
        except psycopg2.Error as e:
            print(f"❌ Database connection failed: {e}")
            self.conn = None

    def get_cursor(self):
        """Ensure a valid cursor, reconnecting if needed."""
        self.connect_db()  # Reconnect if needed
        if self.conn is None:
            raise psycopg2.InterfaceError("Database connection is not available")
        return self.conn.cursor()

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None  # Set to None so it can reconnect later
