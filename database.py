import os
import time
import psycopg2
from psycopg2 import OperationalError
import psycopg2.extras
import hashlib
import uuid
from datetime import datetime
from dotenv import load_dotenv

class Database:
    def __init__(self):
        load_dotenv()
        self.database_url = os.getenv("DATABASE_URL")
        self.max_retries = 3
        self.connect_with_retry()

    def connect_with_retry(self):
        retries = 0
        while retries < self.max_retries:
            try:
                self.conn = psycopg2.connect(self.database_url, sslmode="require")
                print(f"✅ Successfully connected to Neon DB! (Attempt {retries+1})")
                self.init_db()
                return
            except OperationalError as e:
                retries += 1
                print(f"❌ Database connection failed (Attempt {retries}): {e}")
                if retries < self.max_retries:
                    time.sleep(2)  # Wait 2 seconds before retrying
                else:
                    raise  # Re-raise the exception if max retries reached

    def ensure_connection(self):
        try:
            # Test if connection is alive
            with self.conn.cursor() as c:
                c.execute("SELECT 1")
        except (OperationalError, psycopg2.InterfaceError):
            print("🔄 Database connection lost, reconnecting...")
            self.connect_with_retry()
    
    def init_db(self):
        with self.conn.cursor() as c:
            # Create users table
            c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                api_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
            ''')

            # Create conversations table
            c.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id UUID PRIMARY KEY,
                user_id UUID NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            ''')

            # Create messages table
            c.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id UUID PRIMARY KEY,
                conversation_id UUID NOT NULL,
                user_id UUID NOT NULL,
                is_user BOOLEAN NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            ''')

            self.conn.commit()

    def close(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            print("Database connection closed")

    # User authentication functions
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, password, email, api_key):
        self.ensure_connection()
        try:
            user_id = uuid.uuid4()
            password_hash = self.hash_password(password)
            with self.conn.cursor() as c:
                c.execute(
                    "INSERT INTO users (user_id, username, password_hash, email, api_key, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, username, password_hash, email, api_key, datetime.now())
                )
                self.conn.commit()
                return True, user_id
        except psycopg2.IntegrityError:
            self.conn.rollback()
            return False, "Username or email already exists"
        except Exception as e:
            self.conn.rollback()
            return False, f"Error during registration: {str(e)}"

    def login_user(self, username, password):
        self.ensure_connection()
        try:
            with self.conn.cursor() as c:
                c.execute("SELECT user_id, password_hash FROM users WHERE username = %s", (username,))
                result = c.fetchone()

                if result and result[1] == self.hash_password(password):
                    # Update last login time
                    c.execute("UPDATE users SET last_login = %s WHERE user_id = %s", (datetime.now(), result[0]))
                    self.conn.commit()
                    return True, result[0]
                return False, "Invalid username or password"
        except Exception as e:
            self.conn.rollback()
            return False, f"Login error: {str(e)}"

    def get_user_api_key(self, user_id):
        self.ensure_connection()
        with self.conn.cursor() as c:
            c.execute("SELECT api_key FROM users WHERE user_id = %s", (user_id,))
            result = c.fetchone()
            return result[0] if result else None

    # Conversation management functions
    def create_conversation(self, user_id, title):
        self.ensure_connection()
        conversation_id = uuid.uuid4()
        with self.conn.cursor() as c:
            c.execute(
                "INSERT INTO conversations (conversation_id, user_id, title, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                (conversation_id, user_id, title, datetime.now(), datetime.now())
            )
            self.conn.commit()
            return conversation_id

    def get_user_conversations(self, user_id):
        self.ensure_connection()
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as c:
            c.execute(
                "SELECT conversation_id, title, created_at FROM conversations WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,)
            )
            return c.fetchall()

    def get_conversation_messages(self, conversation_id):
        self.ensure_connection()
        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as c:
            c.execute(
                "SELECT message_id, is_user, content, timestamp FROM messages WHERE conversation_id = %s ORDER BY timestamp",
                (conversation_id,)
            )
            return c.fetchall()

    def add_message(self, conversation_id, user_id, is_user, content):
        self.ensure_connection()
        message_id = uuid.uuid4()
        with self.conn.cursor() as c:
            c.execute(
                "INSERT INTO messages (message_id, conversation_id, user_id, is_user, content, timestamp) VALUES (%s, %s, %s, %s, %s, %s)",
                (message_id, conversation_id, user_id, is_user, content, datetime.now())
            )
            c.execute(
                "UPDATE conversations SET updated_at = %s WHERE conversation_id = %s",
                (datetime.now(), conversation_id)
            )
            self.conn.commit()
            return message_id

    def rename_conversation(self, conversation_id, new_title):
        self.ensure_connection()
        with self.conn.cursor() as c:
            c.execute(
                "UPDATE conversations SET title = %s, updated_at = %s WHERE conversation_id = %s",
                (new_title, datetime.now(), conversation_id)
            )
            self.conn.commit()

    def delete_conversation(self, conversation_id):
        self.ensure_connection()
        with self.conn.cursor() as c:
            c.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
            c.execute("DELETE FROM conversations WHERE conversation_id = %s", (conversation_id,))
            self.conn.commit()
    
    # Method to check Neon database connection and tables
    def check_neon_connection(self):
        """
        Performs a comprehensive check of the Neon database connection and tables.
        Returns a dictionary with status information.
        """
        status = {
            "connection": False,
            "tables": {
                "users": False,
                "conversations": False,
                "messages": False
            },
            "errors": []
        }
        
        try:
            # Test the connection
            self.ensure_connection()
            status["connection"] = True
            
            # Check each table
            with self.conn.cursor() as c:
                # Check users table
                try:
                    c.execute("SELECT COUNT(*) FROM users")
                    users_count = c.fetchone()[0]
                    status["tables"]["users"] = True
                    status["users_count"] = users_count
                except Exception as e:
                    status["errors"].append(f"Users table error: {str(e)}")
                
                # Check conversations table
                try:
                    c.execute("SELECT COUNT(*) FROM conversations")
                    convs_count = c.fetchone()[0]
                    status["tables"]["conversations"] = True
                    status["conversations_count"] = convs_count
                except Exception as e:
                    status["errors"].append(f"Conversations table error: {str(e)}")
                
                # Check messages table
                try:
                    c.execute("SELECT COUNT(*) FROM messages")
                    msgs_count = c.fetchone()[0]
                    status["tables"]["messages"] = True
                    status["messages_count"] = msgs_count
                except Exception as e:
                    status["errors"].append(f"Messages table error: {str(e)}")
                
                # Check database version and connection info
                try:
                    c.execute("SELECT version()")
                    version = c.fetchone()[0]
                    status["db_version"] = version
                    
                    # Get connection details
                    c.execute("SELECT current_database(), current_user")
                    db_info = c.fetchone()
                    status["database_name"] = db_info[0]
                    status["database_user"] = db_info[1]
                except Exception as e:
                    status["errors"].append(f"Database info error: {str(e)}")
                
        except Exception as e:
            status["errors"].append(f"Connection error: {str(e)}")
            
        return status
