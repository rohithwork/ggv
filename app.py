import streamlit as st
import time
import os
from datetime import datetime
import uuid
from dotenv import load_dotenv

# Import custom modules
from database import Database
from rag_system import RAGSystem

# Load environment variables
load_dotenv()

# Streamlit UI Components
def create_sidebar():
    with st.sidebar:
        # Check if the directory exists, try both spellings
        if os.path.exists("assets/company_logo.png"):
            st.image("assets/company_logo.png", width=150)
        elif os.path.exists("assests/company_logo.png"):
            st.image("assests/company_logo.png", width=150)
        else:
            st.title("Golden Gate Ventures")  # Fallback if image not found
            
        st.markdown("Internal Knowledge Assistant")
        
        if st.session_state.get("authenticated", False):
            st.button("New Chat", on_click=start_new_chat)
            
            # Display user's conversations
            st.subheader("Your Conversations")
            try:
                conversations = st.session_state.db.get_user_conversations(st.session_state.user_id)
                
                for conv in conversations:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        if st.button(f"{conv[1]}", key=f"conv_{conv[0]}"):
                            st.session_state.current_conversation_id = conv[0]
                            st.session_state.conversation_title = conv[1]
                            load_conversation_messages()
                    with col2:
                        if st.button("🗑️", key=f"del_{conv[0]}"):
                            st.session_state.db.delete_conversation(conv[0])
                            if st.session_state.current_conversation_id == conv[0]:
                                start_new_chat()
                            st.rerun()
            except Exception as e:
                st.error(f"Error loading conversations: {str(e)}")
            
            st.divider()
            
            # Add database connection status checker
            if st.button("Check Database Status"):
                status = st.session_state.db.check_neon_connection()
                if status["connection"]:
                    st.success("✅ Connected to Neon DB!")
                    st.write(f"Database: {status.get('database_name', 'N/A')}")
                    st.write(f"Users: {status.get('users_count', 0)}")
                    st.write(f"Conversations: {status.get('conversations_count', 0)}")
                    st.write(f"Messages: {status.get('messages_count', 0)}")
                else:
                    st.error("❌ Connection failed")
                    for err in status["errors"]:
                        st.write(err)
            
            if st.button("Logout"):
                # Clean up resources before logout
                if "db" in st.session_state:
                    try:
                        st.session_state.db.close()
                    except:
                        pass
                
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        else:
            st.info("Please login or register to continue.")

def load_conversation_messages():
    if st.session_state.get("current_conversation_id"):
        try:
            # Get ALL messages for this conversation
            messages = st.session_state.db.get_conversation_messages(st.session_state.current_conversation_id)
            st.session_state.chat_messages = messages
            
            # Use the complete conversation history
            st.session_state.chat_history = messages
            
            # Update the messages for the chat UI
            st.session_state.messages = []
            for msg in messages:
                is_user = msg[1]
                content = msg[2]
                role = "user" if is_user else "assistant"
                st.session_state.messages.append({"role": role, "content": content})
        except Exception as e:
            st.error(f"Error loading conversation messages: {str(e)}")
            # Attempt to reconnect if needed
            if "db" in st.session_state:
                st.session_state.db.ensure_connection()

def start_new_chat():
    try:
        # Create a new conversation with a default title
        default_title = f"New chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        conversation_id = st.session_state.db.create_conversation(
            st.session_state.user_id, 
            default_title
        )
        st.session_state.current_conversation_id = conversation_id
        st.session_state.conversation_title = default_title
        st.session_state.chat_messages = []
        st.session_state.chat_history = []
        st.session_state.messages = []  # Clear the chat UI messages
        # Flag to indicate the title needs to be updated after first message
        st.session_state.needs_title_update = True
    except Exception as e:
        st.error(f"Error creating new chat: {str(e)}")
        # Attempt to reconnect if needed
        if "db" in st.session_state:
            st.session_state.db.ensure_connection()

def display_auth_page():
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login"):
            if username and password:
                try:
                    success, result = st.session_state.db.login_user(username, password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_id = result
                        st.session_state.username = username
                        
                        # Get user's API key and initialize RAG system
                        api_key = st.session_state.db.get_user_api_key(result)
                        st.session_state.api_key = api_key
                        st.session_state.rag_system = RAGSystem(api_key)
                        
                        # Start with a new chat
                        start_new_chat()
                        st.rerun()
                    else:
                        st.error(result)
                except Exception as e:
                    st.error(f"Login error: {str(e)}")
                    # Attempt to reconnect if needed
                    if "db" in st.session_state:
                        st.session_state.db.ensure_connection()
            else:
                st.warning("Please enter both username and password")
    
    with tab2:
        st.subheader("Register")
        new_username = st.text_input("Username", key="reg_username")
        new_email = st.text_input("Email", key="reg_email")
        new_password = st.text_input("Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
        api_key = st.text_input("Cohere API Key", key="reg_api_key", 
                               help="Enter your Cohere API key. This will be used for retrieving and generating responses.")
        
        if st.button("Register"):
            if new_username and new_email and new_password and api_key:
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    try:
                        success, result = st.session_state.db.register_user(new_username, new_password, new_email, api_key)
                        if success:
                            st.success("Registration successful! Please login.")
                            # Switch to the login tab
                            st.rerun()
                        else:
                            st.error(result)
                    except Exception as e:
                        st.error(f"Registration error: {str(e)}")
                        # Attempt to reconnect if needed
                        if "db" in st.session_state:
                            st.session_state.db.ensure_connection()
            else:
                st.warning("Please fill all fields")

def display_chat_interface():
    # Allow user to edit conversation title
    new_title = st.text_input(
        "Conversation Title", 
        value=st.session_state.get("conversation_title", "New Chat"),
        key="title_input"
    )
    
    if new_title != st.session_state.get("conversation_title", ""):
        try:
            st.session_state.db.rename_conversation(st.session_state.current_conversation_id, new_title)
            st.session_state.conversation_title = new_title
        except Exception as e:
            st.error(f"Error updating conversation title: {str(e)}")
            # Attempt to reconnect if needed
            if "db" in st.session_state:
                st.session_state.db.ensure_connection()
    
    # Initialize messages container in session state if not present
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # Load previous messages into the format expected by st.chat_message
        if "chat_messages" in st.session_state and st.session_state.chat_messages:
            for msg in st.session_state.chat_messages:
                is_user = msg[1]
                content = msg[2]
                role = "user" if is_user else "assistant"
                st.session_state.messages.append({"role": role, "content": content})
    
    # Display chat messages using Streamlit's chat_message component
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message..."):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message immediately
        with st.chat_message("user"):
            st.markdown(prompt)
        
        try:
            # Save user message to database
            st.session_state.db.add_message(
                st.session_state.current_conversation_id,
                st.session_state.user_id,
                True,  # is_user
                prompt
            )
            
            # IMPORTANT: Get ALL messages for this conversation
            # Get the complete conversation history from the database
            all_messages = st.session_state.db.get_conversation_messages(st.session_state.current_conversation_id)
            st.session_state.chat_messages = all_messages
            st.session_state.chat_history = all_messages  # Use the full history
            
            # Format the chat history correctly for the RAG system
            chat_history = [(msg[0], msg[1], msg[2], msg[3]) for msg in st.session_state.chat_history]
            
            # Get response from RAG system
            try:
                stream, sources = st.session_state.rag_system.generate_response_stream(prompt, chat_history)
                
                # Display assistant response
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    full_response = ""
                    
                    # Stream the response
                    for event in stream:
                        if hasattr(event, "type") and event.type == "content-delta":
                            delta_text = event.delta.message.content.text
                            full_response += delta_text
                            # Update the response in real-time
                            response_placeholder.markdown(full_response + "▌")
                            time.sleep(0.01)  # Small delay for smoother streaming
                        
                        # Handle end of stream
                        if hasattr(event, "type") and event.type == "message-end":
                            # Show final response without cursor
                            response_placeholder.markdown(full_response)
                    
                    # Save assistant response to database and session state
                    st.session_state.db.add_message(
                        st.session_state.current_conversation_id,
                        st.session_state.user_id,
                        False,  # is_user
                        full_response
                    )
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                error_message = f"An error occurred: {str(e)}"
                with st.chat_message("assistant"):
                    st.error(error_message)
                
                # Save error message to database
                st.session_state.db.add_message(
                    st.session_state.current_conversation_id,
                    st.session_state.user_id,
                    False,  # is_user
                    error_message
                )
                st.session_state.messages.append({"role": "assistant", "content": error_message})
        except Exception as e:
            st.error(f"Error processing message: {str(e)}")
            # Attempt to reconnect
            if "db" in st.session_state:
                st.session_state.db.ensure_connection()

# Main Streamlit App
def main():
    st.set_page_config(
        page_title="Golden Gate Ventures Assistant",
        page_icon="🌉",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize database connection
    if "db" not in st.session_state:
        try:
            st.session_state.db = Database()
            
            # Add a database status check on startup
            status = st.session_state.db.check_neon_connection()
            if not status["connection"]:
                st.error("❌ Initial database connection check failed:")
                for err in status["errors"]:
                    st.write(err)
                st.info("The app will continue to retry connecting to the database.")
                
        except Exception as e:
            st.error(f"Failed to connect to the database: {str(e)}")
            st.info("Please check your DATABASE_URL in the .env file and ensure the PostgreSQL server is running.")
            
            # Add a retry button
            if st.button("Retry Database Connection"):
                try:
                    st.session_state.db = Database()
                    st.success("Connection successful!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Retry failed: {str(e)}")
            
            return
    
    # Create sidebar
    create_sidebar()
    
    # Main content
    if st.session_state.get("authenticated", False):
        if "current_conversation_id" not in st.session_state:
            start_new_chat()
        
        # Display chat interface
        display_chat_interface()
    else:
        display_auth_page()

# Add a function to diagnose Neon connectivity issues
def diagnose_neon_connectivity():
    st.title("Neon Database Connection Diagnostics")
    
    # Check environment variables
    st.subheader("Environment Variables")
    if "DATABASE_URL" in os.environ:
        masked_url = os.environ["DATABASE_URL"]
        # Mask the password and other sensitive parts
        if "@" in masked_url:
            parts = masked_url.split("@")
            prefix = parts[0].split("://")
            if len(prefix) > 1:
                protocol = prefix[0]
                credentials = "://***:***"
                masked_url = protocol + credentials + "@" + parts[1]
        st.success(f"✅ DATABASE_URL is set: {masked_url}")
    else:
        st.error("❌ DATABASE_URL environment variable is missing")
    
    # Test connection
    if st.button("Test Connection"):
        try:
            db = Database()
            status = db.check_neon_connection()
            
            if status["connection"]:
                st.success("✅ Successfully connected to Neon DB!")
                
                # Display database info
                st.subheader("Database Information")
                st.write(f"Database: {status.get('database_name', 'N/A')}")
                st.write(f"User: {status.get('database_user', 'N/A')}")
                st.write(f"Version: {status.get('db_version', 'N/A')}")
                
                # Display table info
                st.subheader("Tables Status")
                tables_status = status["tables"]
                for table, exists in tables_status.items():
                    status_icon = "✅" if exists else "❌"
                    st.write(f"{status_icon} {table.capitalize()}: {'Found' if exists else 'Not found'}")
                
                if "users_count" in status:
                    st.write(f"Users count: {status['users_count']}")
                if "conversations_count" in status:
                    st.write(f"Conversations count: {status['conversations_count']}")
                if "messages_count" in status:
                    st.write(f"Messages count: {status['messages_count']}")
                
                # Check for any warnings
                if status["errors"]:
                    st.warning("⚠️ Connection successful but with warnings:")
                    for error in status["errors"]:
                        st.write(f"- {error}")
            else:
                st.error("❌ Connection to Neon DB failed")
                if status["errors"]:
                    st.write("Errors:")
                    for error in status["errors"]:
                        st.write(f"- {error}")
                
                st.subheader("Troubleshooting Steps")
                st.markdown("""
                1. Check that your Neon database is active and not in hibernation
                2. Verify the DATABASE_URL is correct in your .env file
                3. Make sure your IP is allowed in Neon's firewall settings
                4. Check if you've reached connection limits on your Neon plan
                5. Try restarting your Neon database
                """)
            
            # Clean up
            db.close()
        except Exception as e:
            st.error(f"❌ Connection test failed: {str(e)}")
            
            st.subheader("Troubleshooting Steps")
            st.markdown("""
            1. Verify your .env file has the correct DATABASE_URL
            2. Check your network connection
            3. Make sure the psycopg2 package is installed: `pip install psycopg2-binary`
            4. Verify the Neon database server is running and accessible
            """)

# If this script is run directly, call the main function
if __name__ == "__main__":
    if os.environ.get("DIAGNOSE_MODE", "").lower() in ("true", "1", "yes"):
        diagnose_neon_connectivity()
    else:
        main()
