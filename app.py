import streamlit as st
import time
import os
from datetime import datetime
import uuid

# Import custom modules
from database import Database
from rag_system import RAGSystem

# Configuration for Neon database
def get_db_connection():
    # Check for the database URL in session state first (for testing)
    db_url = st.session_state.get("db_url")
    
    # If not in session state, try environment variable
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        # If no URL found, allow user to enter it manually
        with st.sidebar:
            if "db_config_shown" not in st.session_state:
                st.session_state.db_config_shown = True
                st.info("Database configuration needed")
            
            db_url = st.text_input("Neon Database URL", 
                                   key="manual_db_url",
                                   help="Enter your Neon database connection URL",
                                   type="password")
            
            if db_url and st.button("Connect"):
                st.session_state.db_url = db_url
                return Database(db_url)
        
        # Return None if no URL is available yet
        return None
    
    # Return database connection with the URL
    return Database(db_url)

# Streamlit UI Components
def create_sidebar():
    with st.sidebar:
        st.image("assests//company_logo.png", width=150)
        st.title("Golden Gate Ventures")
        st.markdown("Internal Knowledge Assistant")
        
        if st.session_state.get("authenticated", False):
            st.button("New Chat", on_click=start_new_chat)
            
            # Display user's conversation.
            # Display user's conversations
            st.subheader("Your Conversations")
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
                        # Reset current conversation if we're deleting the active one
                        if st.session_state.current_conversation_id == conv[0]:
                        # Clear conversation-specific session state
                            st.session_state.current_conversation_id = None
                            st.session_state.conversation_title = None
                            st.session_state.chat_messages = []
                            st.session_state.chat_history = []
                            st.session_state.messages = []
                            # Start a new chat session
                            start_new_chat()
                            # Force a full rerun to update the sidebar
                        st.rerun()
            
            st.divider()
            if st.button("Logout"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        else:
            st.info("Please login or register to continue.")

def load_conversation_messages():
    if st.session_state.get("current_conversation_id"):
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

def start_new_chat():
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

def display_auth_page():
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login"):
            if username and password:
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
                    success, result = st.session_state.db.register_user(new_username, new_password, new_email, api_key)
                    if success:
                        st.success("Registration successful! Please login.")
                        # Switch to the login tab
                        st.rerun()
                    else:
                        st.error(result)
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
        st.session_state.db.rename_conversation(st.session_state.current_conversation_id, new_title)
        st.session_state.conversation_title = new_title
    
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
    
    # Save user message to database
        st.session_state.db.add_message(
            st.session_state.current_conversation_id,
            st.session_state.user_id,
            True,  # is_user
            prompt
        )
    
    # Update title after first message
        if st.session_state.get("needs_title_update", False) and st.session_state.get("rag_system"):
            # Generate a title based on the first message
            new_title = st.session_state.rag_system.generate_chat_title(prompt)
            # Update the conversation title in the database
            st.session_state.db.rename_conversation(st.session_state.current_conversation_id, new_title)
            # Update the title in session state
            st.session_state.conversation_title = new_title
            # Reset the flag
            st.session_state.needs_title_update = False
        
        # IMPORTANT: Get ALL messages for this conversation
        # Get the complete conversation history from the database
        all_messages = st.session_state.db.get_conversation_messages(st.session_state.current_conversation_id)
        st.session_state.chat_messages = all_messages
        st.session_state.chat_history = all_messages  # Use the full history
        
        # Format the chat history correctly for the RAG system
        chat_history = [(msg[0], msg[1], msg[2], msg[3]) for msg in st.session_state.chat_history]
        
        # Get response from RAG system
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
        
        # Update the UI messages
        # We're not limiting what's shown to the user, show the full conversation
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
            
        st.session_state.chat_messages.append((str(uuid.uuid4()), True, prompt, datetime.now()))
        st.session_state.chat_messages.append((str(uuid.uuid4()), False, full_response, datetime.now()))

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
        st.session_state.db = get_db_connection()
        
        # If no database connection is available yet, show only the database configuration UI
        if st.session_state.db is None:
            st.warning("Please configure your Neon database connection to continue")
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

if __name__ == "__main__":
    main()
