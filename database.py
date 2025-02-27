import os
import uuid
import time
import psycopg2
import psycopg2.pool
import hashlib
from datetime import datetime
from dotenv import load_dotenv


class Database:
    """Database class for managing user authentication and API keys with connection pooling."""

    def __init__(self):
        """Initializes the database connection pool."""
        load_dotenv()
        self.database_url = os.getenv("DATABASE_URL")

        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment variables")

        # Create a connection pool (1 min connection, 10 max)
        self.pool = psycopg2.pool.SimpleConnectionPool(
            1, 10, self.database_url, sslmode="require"
        )

    def get_connection(self):
        """Gets a connection from the pool, reconnecting if necessary."""
        try:
            return self.pool.getconn()
        except psycopg2.Error:
            print("⚠️ Database connection lost. Trying to reconnect...")
            self.pool = psycopg2.pool.SimpleConnectionPool(
                1, 10, self.database_url, sslmode="require"
            )
            return self.pool.getconn()

    def release_connection(self, conn):
        """Releases a connection back to the pool."""
        if conn:
            self.pool.putconn(conn)

    def get_cursor(self):
        """Returns a database cursor, ensuring connection stability."""
        conn = self.get_connection()
        return conn.cursor(), conn  # Return both cursor and connection

    def execute_query(self, query, params=None, retries=3):
        """Executes a query with automatic reconnection and retries."""
        for attempt in range(retries):
            conn = None
            try:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()

                # Fetch results if it's a SELECT query
                if query.strip().lower().startswith("select"):
                    return cursor.fetchall()
                return True
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                print(f"⚠️ Database error: {e}. Retrying ({attempt + 1}/{retries})...")
                time.sleep(2)  # Wait before retrying
            finally:
                if conn:
                    self.release_connection(conn)
        return None  # If all retries fail

    def hash_password(self, password):
        """Hashes a password using SHA-256."""
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, password, email, api_key):
        """Registers a new user."""
        user_id = str(uuid.uuid4())
        password_hash = self.hash_password(password)
        created_at = datetime.now()

        query = """
        INSERT INTO users (user_id, username, password_hash, email, api_key, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (user_id, username, password_hash, email, api_key, created_at)

        result = self.execute_query(query, params)
        return (True, user_id) if result else (False, "Username or email already exists")

    def authenticate_user(self, username, password):
        """Authenticates a user by checking the username and password hash."""
        query = "SELECT user_id, password_hash FROM users WHERE username = %s"
        params = (username,)

        result = self.execute_query(query, params)
        if not result:
            return False, "User not found"

        user_id, stored_hash = result[0]
        if self.hash_password(password) == stored_hash:
            return True, user_id
        return False, "Invalid credentials"

    def get_api_key(self, user_id):
        """Retrieves the API key for a given user ID."""
        query = "SELECT api_key FROM users WHERE user_id = %s"
        params = (user_id,)

        result = self.execute_query(query, params)
        return result[0][0] if result else None
