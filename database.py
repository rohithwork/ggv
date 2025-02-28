import psycopg2
import hashlib
import uuid
from datetime import datetime
import time
import os
from sqlalchemy import create_engine, text
from contextlib import contextmanager

class Database:
    def __init__(self, connection_string=None):
        # Use environment variable or provided connection string
        self.connection_string = connection_string or os.environ.get('NEON_CONNECTION_STRING')
        
        if not self.connection_string:
            raise ValueError("Neon database connection string not provided")
        
        # Initialize the database (create tables if they don't exist)
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager to handle database connections with retry logic"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Create a new connection
                conn = psycopg2.connect(self.connection_string)
                conn.autocommit = False
                
                # Yield the connection to the caller
                yield conn
                
                # If we reach here without exception, break the retry loop
                break
                
            except psycopg2.OperationalError as e:
                # Connection error occurred
                if attempt < max_retries - 1:
                    # If not the last attempt, wait and retry
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # If this was the last attempt, re-raise the exception
                    raise e
            
            finally:
                # Make sure to close the connection if it was created
                if 'conn' in locals() and conn is not None:
                    conn.close()
    
    def execute_query(self, query, params=None, fetch=False, commit=True):
        """Execute a query with automatic connection handling and retries"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params or ())
                
                if fetch:
                    result = cursor.fetchall()
                else:
                    result = None
                    
                if commit:
                    conn.commit()
                    
                return result
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                cursor.close()
    
    def init_db(self):
        """Initialize database tables if they don't exist"""
        # Create users table with API key field
        users_table = '''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            api_key TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
        '''
        
        # Create conversations table
        conversations_table = '''
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        '''
        
        # Create messages table
        messages_table = '''
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
        '''
        
        self.execute_query(users_table)
        self.execute_query(conversations_table)
        self.execute_query(messages_table)
    
    # User authentication functions
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password, email, api_key):
        try:
            user_id = str(uuid.uuid4())
            password_hash = self.hash_password(password)
            
            query = '''
            INSERT INTO users (user_id, username, password_hash, email, api_key, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            '''
            
            self.execute_query(
                query,
                (user_id, username, password_hash, email, api_key, datetime.now())
            )
            
            return True, user_id
            
        except psycopg2.errors.UniqueViolation:
            return False, "Username or email already exists"
        except Exception as e:
            return False, str(e)
    
    def login_user(self, username, password):
        try:
            query = "SELECT user_id, password_hash FROM users WHERE username = %s"
            result = self.execute_query(query, (username,), fetch=True)
            
            if result and result[0][1] == self.hash_password(password):
                # Update last login time
                update_query = "UPDATE users SET last_login = %s WHERE user_id = %s"
                self.execute_query(update_query, (datetime.now(), result[0][0]))
                
                return True, result[0][0]
            return False, "Invalid username or password"
            
        except Exception as e:
            return False, f"Login error: {str(e)}"
    
    def get_user_api_key(self, user_id):
        try:
            query = "SELECT api_key FROM users WHERE user_id = %s"
            result = self.execute_query(query, (user_id,), fetch=True)
            
            if result:
                return result[0][0]
            return None
            
        except Exception:
            return None
    
    # Conversation management functions
    def create_conversation(self, user_id, title):
        conversation_id = str(uuid.uuid4())
        now = datetime.now()
        
        query = '''
        INSERT INTO conversations (conversation_id, user_id, title, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
        '''
        
        self.execute_query(query, (conversation_id, user_id, title, now, now))
        
        return conversation_id
    
    def get_user_conversations(self, user_id):
        query = '''
        SELECT conversation_id, title, created_at 
        FROM conversations 
        WHERE user_id = %s 
        ORDER BY updated_at DESC
        '''
        
        try:
            return self.execute_query(query, (user_id,), fetch=True)
        except Exception:
            # Return empty list if query fails
            return []
    
    def get_conversation_messages(self, conversation_id):
        query = '''
        SELECT message_id, is_user, content, timestamp 
        FROM messages 
        WHERE conversation_id = %s 
        ORDER BY timestamp
        '''
        
        try:
            return self.execute_query(query, (conversation_id,), fetch=True)
        except Exception:
            # Return empty list if query fails
            return []
    
    def add_message(self, conversation_id, user_id, is_user, content):
        try:
            message_id = str(uuid.uuid4())
            now = datetime.now()
            
            # Insert message
            message_query = '''
            INSERT INTO messages (message_id, conversation_id, user_id, is_user, content, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            '''
            
            self.execute_query(
                message_query, 
                (message_id, conversation_id, user_id, is_user, content, now)
            )
            
            # Update conversation's updated_at timestamp
            update_query = '''
            UPDATE conversations SET updated_at = %s WHERE conversation_id = %s
            '''
            
            self.execute_query(update_query, (now, conversation_id))
            
            return message_id
            
        except Exception as e:
            print(f"Error adding message: {str(e)}")
            # Create a dummy message ID to prevent further errors
            return str(uuid.uuid4())
    
    def rename_conversation(self, conversation_id, new_title):
        query = '''
        UPDATE conversations SET title = %s, updated_at = %s WHERE conversation_id = %s
        '''
        
        self.execute_query(query, (new_title, datetime.now(), conversation_id))
    
    def delete_conversation(self, conversation_id):
        try:
            # First delete all messages in the conversation
            self.execute_query("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
            
            # Then delete the conversation
            self.execute_query("DELETE FROM conversations WHERE conversation_id = %s", (conversation_id,))
            
            return True
        except Exception as e:
            print(f"Error deleting conversation: {str(e)}")
            return False
