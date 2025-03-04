import psycopg2
import hashlib
import uuid
from datetime import datetime
import os
from urllib.parse import urlparse

class Database:
    def __init__(self, db_url=None):
        # If no URL is provided, try to get it from environment variable
        if not db_url:
            db_url = os.environ.get('DATABASE_URL')
            
        if not db_url:
            raise ValueError("Database URL not provided and DATABASE_URL environment variable not set")
            
        # Parse the connection URL
        parsed_url = urlparse(db_url)
        
        # Connect to Neon PostgreSQL
        self.conn = psycopg2.connect(
            host=parsed_url.hostname,
            port=parsed_url.port,
            dbname=parsed_url.path[1:],  # Remove leading slash
            user=parsed_url.username,
            password=parsed_url.password,
            sslmode='require'  # Neon requires SSL
        )
        
        self.init_db()
        self.init_admin_users()
    
    def init_db(self):
        c = self.conn.cursor()
        
        # Create users table with API key field and is_admin flag
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
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
    
    def init_admin_users(self):
        """Initialize default admin users if they don't exist"""
        admin_users = [
            {
                "email": "jeff@goldengate.vc",
                "password": "admin123",  # You should use a more secure password in production
                "api_key": "uWLYCAHh1pWqCjNgMZwKsSINWbEwjKELQRk21H6Y",
                "is_admin": True
            },
            {
                "email": "jeevananthamrohith2004@gmail.com",
                "password": "admin123",  # You should use a more secure password in production
                "api_key": "jA1KJPrqC4CI68GoivqmKRsWIxro7lF9NpRSZ8oL",
                "is_admin": True
            }
        ]
        
        for admin in admin_users:
            # Check if admin already exists
            c = self.conn.cursor()
            c.execute("SELECT user_id FROM users WHERE email = %s", (admin["email"],))
            if not c.fetchone():
                # Create the admin user
                user_id = str(uuid.uuid4())
                password_hash = self.hash_password(admin["password"])
                
                c.execute(
                    "INSERT INTO users (user_id, email, password_hash, api_key, is_admin, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, admin["email"], password_hash, admin["api_key"], admin["is_admin"], datetime.now())
                )
                self.conn.commit()
    
    def close(self):
        self.conn.close()
    
    # User authentication functions
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, email, password, api_key, is_admin=False):
        """Register a new user (only for admin users)"""
        try:
            user_id = str(uuid.uuid4())
            password_hash = self.hash_password(password)
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO users (user_id, email, password_hash, api_key, is_admin, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, email, password_hash, api_key, is_admin, datetime.now())
            )
            self.conn.commit()
            return True, user_id
        except psycopg2.IntegrityError:
            return False, "Email already exists"
    
    def login_user(self, email, password):
        """Login a user with email and password"""
        c = self.conn.cursor()
        c.execute("SELECT user_id, password_hash, is_admin FROM users WHERE email = %s", (email,))
        result = c.fetchone()
        
        if result and result[1] == self.hash_password(password):
            # Update last login time
            c.execute("UPDATE users SET last_login = %s WHERE user_id = %s", (datetime.now(), result[0]))
            self.conn.commit()
            return True, {"user_id": result[0], "is_admin": result[2]}
        return False, "Invalid email or password"
    
    def get_user_details(self, user_id):
        """Get user details including email and admin status"""
        c = self.conn.cursor()
        c.execute("SELECT email, is_admin, api_key FROM users WHERE user_id = %s", (user_id,))
        result = c.fetchone()
        if result:
            return {
                "email": result[0],
                "is_admin": result[1],
                "api_key": result[2]
            }
        return None
    
    def get_user_api_key(self, user_id):
        c = self.conn.cursor()
        c.execute("SELECT api_key FROM users WHERE user_id = %s", (user_id,))
        result = c.fetchone()
        if result:
            return result[0]
        return None
    
    def get_all_users(self):
        """Get all users (for admin view)"""
        c = self.conn.cursor()
        c.execute("SELECT user_id, email, is_admin, created_at, last_login FROM users ORDER BY created_at DESC")
        return c.fetchall()
    
    # Conversation management functions
    def create_conversation(self, user_id, title):
        conversation_id = str(uuid.uuid4())
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO conversations (conversation_id, user_id, title, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
            (conversation_id, user_id, title, datetime.now(), datetime.now())
        )
        self.conn.commit()
        return conversation_id
    
    def get_user_conversations(self, user_id, is_admin=False):
        """Get conversations for a user or all conversations if admin"""
        c = self.conn.cursor()
        
        if is_admin:
            # For admin users, return all conversations with user email
            c.execute(
                """
                SELECT c.conversation_id, c.title, c.created_at, u.email 
                FROM conversations c
                JOIN users u ON c.user_id = u.user_id
                ORDER BY c.updated_at DESC
                """
            )
        else:
            # For regular users, return only their conversations
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
    
    def rename_conversation(self, conversation_id, new_title):
        c = self.conn.cursor()
        c.execute(
            "UPDATE conversations SET title = %s, updated_at = %s WHERE conversation_id = %s",
            (new_title, datetime.now(), conversation_id)
        )
        self.conn.commit()
    
    def delete_conversation(self, conversation_id):
        c = self.conn.cursor()
        # First delete all messages in the conversation
        c.execute("DELETE FROM messages WHERE conversation_id = %s", (conversation_id,))
        # Then delete the conversation
        c.execute("DELETE FROM conversations WHERE conversation_id = %s", (conversation_id,))
        self.conn.commit()
    
    def can_access_conversation(self, user_id, conversation_id):
        """Check if a user can access a specific conversation (user owns it or is admin)"""
        c = self.conn.cursor()
        
        # First check if user is admin
        c.execute("SELECT is_admin FROM users WHERE user_id = %s", (user_id,))
        user_result = c.fetchone()
        if user_result and user_result[0]:  # User is admin
            return True
            
        # If not admin, check if user owns the conversation
        c.execute(
            "SELECT 1 FROM conversations WHERE conversation_id = %s AND user_id = %s",
            (conversation_id, user_id)
        )
        return c.fetchone() is not None
