import os
import psycopg2
import hashlib
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Database:
    def __init__(self):
        # Get database connection string from environment variable
        # Format: postgresql://username:password@host:port/database
        self.db_url = os.getenv("DATABASE_URL")
        self.connect()
        self.init_db()
    
    def connect(self):
        # Connect to the PostgreSQL database
        self.conn = psycopg2.connect(self.db_url)
        self.conn.autocommit = False
    
    def init_db(self):
        c = self.conn.cursor()
        
        # Create users table with API key field
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
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
            conversation_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')
        
        # Create messages table
        c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            is_user BOOLEAN NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''')
        
        self.conn.commit()
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    # User authentication functions
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password, email, api_key):
        try:
            user_id = str(uuid.uuid4())
            password_hash = self.hash_password(password)
            c = self.conn.cursor()
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
            return False, str(e)
    
    def login_user(self, username, password):
        try:
            c = self.conn.cursor()
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
            return False, str(e)
    
    def get_user_api_key(self, user_id):
        try:
            c = self.conn.cursor()
            c.execute("SELECT api_key FROM users WHERE user_id = %s", (user_id,))
            result = c.fetchone()
            if result:
                return result[0]
            return None
        except Exception:
            return None
    
    # Conversation management functions
    def create_conversation(self, user_id, title):
        try:
            conversation_id = str(uuid.uuid4())
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO conversations (conversation_id, user_id, title, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                (conversation_id, user_id, title, datetime.now(), datetime.now())
            )
            self.conn.commit()
            return conversation_id
        except Exception as e:
            self.conn.rollback()
            print(f"Error creating conversation: {e}")
            return None
    
    def get_user_conversations(self, user_id):
        try:
            c = self.conn.cursor()
            c.execute(
                "SELECT conversation_id, title, created_at FROM conversations WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,)
            )
            return c.fetchall()
        except Exception as e:
            print(f"Error fetching conversations: {e}")
            return []
    
    def get_conversation_messages(self, conversation_id):
        try:
            c = self.conn.cursor()
            c.execute(
                "SELECT message_id, is_user, content, timestamp FROM messages WHERE conversation_id = %s ORDER BY timestamp",
                (conversation_id,)
            )
            return c.fetchall()
        except Exception as e:
            print(f"Error fetching messages: {e}")
            return []
    
    def add_message(self, conversation_id, user_id, is_user, content):
        try:
            message_id = str(uuid.uuid4())
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO messages (message_id, conversation_id, user_id, is_user, content, timestamp) VALUES (%s, %s, %s, %s, %s, %s)",
                (message_id, conversation_id, user_id, is_user, content, datetime.now())
            )
            # Update conversation's updated_at timestamp
            c.execute(
                "UPDATE conversations SET updated_at = %s WHERE conversation_id = %s",
                (datetime.now(), conversation_id)
            )
            self.conn.commit()
            return message_id
        except Exception as e:
            self.conn.rollback()
            print(f"Error adding message: {e}")
            return None
    
    def rename_conversation(self, conversation_id, new_title):
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE conversations SET title = %s, updated_at = %s WHERE conversation_id = %s",
                (new_title, datetime.now(), conversation_id)
            )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Error renaming conversation: {e}")
    
    def delete_conversation(self, conversation_id):
        try:
            c = self.conn.cursor()
            # First delete all messages in the conversation
            c.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
            # Then delete the conversation
            c.execute("DELETE FROM conversations WHERE conversation_id = %s", (conversation_id,))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Error deleting conversation: {e}")
