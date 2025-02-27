import os
import psycopg2
import hashlib
import uuid
from datetime import datetime
from dotenv import load_dotenv

class Database:
    def __init__(self):
        load_dotenv()
        self.database_url = os.getenv('DATABASE_URL')
        self.conn = psycopg2.connect(self.database_url)
        self.init_db()
    
    def init_db(self):
        c = self.conn.cursor()
        
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
        self.conn.close()
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password, email, api_key):
        try:
            user_id = uuid.uuid4()
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
    
    def login_user(self, username, password):
        c = self.conn.cursor()
        c.execute("SELECT user_id, password_hash FROM users WHERE username = %s", (username,))
        result = c.fetchone()
        
        if result and result[1] == self.hash_password(password):
            c.execute("UPDATE users SET last_login = %s WHERE user_id = %s", (datetime.now(), result[0]))
            self.conn.commit()
            return True, result[0]
        return False, "Invalid username or password"
    
    def get_user_api_key(self, user_id):
        c = self.conn.cursor()
        c.execute("SELECT api_key FROM users WHERE user_id = %s", (user_id,))
        result = c.fetchone()
        return result[0] if result else None
    
    def create_conversation(self, user_id, title):
        conversation_id = uuid.uuid4()
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO conversations (conversation_id, user_id, title, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
            (conversation_id, user_id, title, datetime.now(), datetime.now())
        )
        self.conn.commit()
        return conversation_id
    
    def get_user_conversations(self, user_id):
        c = self.conn.cursor()
        c.execute(
            "SELECT conversation_id, title, created_at FROM conversations WHERE user_id = %s ORDER BY updated_at DESC",
            (user_id,)
        )
        return c.fetchall()
    
    def get_conversation_messages(self, conversation_id):
        c = self.conn.cursor()
        c.execute(
            "SELECT message_id, is_user, content, timestamp FROM messages WHERE conversation_id = %s ORDER BY timestamp",
            (conversation_id,)
        )
        return c.fetchall()
    
    def add_message(self, conversation_id, user_id, is_user, content):
        message_id = uuid.uuid4()
        c = self.conn.cursor()
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
        c = self.conn.cursor()
        c.execute(
            "UPDATE conversations SET title = %s, updated_at = %s WHERE conversation_id = %s",
            (new_title, datetime.now(), conversation_id)
        )
        self.conn.commit()
    
    def delete_conversation(self, conversation_id):
        c = self.conn.cursor()
        c.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
        c.execute("DELETE FROM conversations WHERE conversation_id = %s", (conversation_id,))
        self.conn.commit()
