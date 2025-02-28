import streamlit as st
import time
import os
from datetime import datetime
import uuid
import pandas as pd
from PIL import Image
import requests
import json

# Import custom modules
from database import Database
from rag_system import RAGSystem

# Load Lottie animation
def load_lottie_url(url: str):
    try:
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    except:
        return None

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
            
            with st.form(key="db_config_form"):
                db_url = st.text_input("Neon Database URL", 
                                    key="manual_db_url",
                                    help="Enter your Neon database connection URL",
                                    type="password")
                
                submit_button = st.form_submit_button(label="Connect")
                if submit_button and db_url:
                    st.session_state.db_url = db_url
                    return Database(db_url)
        
        # Return None if no URL is available yet
        return None
    
    # Return database connection with the URL
    return Database(db_url)

# Streamlit UI Components
def create_sidebar():
    with st.sidebar:
        # Logo and title
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image("assests//company_logo.png", width=50)
        with col2:
            st.markdown("### Golden Gate Ventures")
        
        # Subtitle
        st.markdown("#### Internal Knowledge Assistant")
        
        # Dark mode toggle (using native Streamlit components)
        dark_mode = st.toggle("Dark Mode", value=st.session_state.get("dark_mode", False), key="dark_mode")
        if dark_mode != st.session_state.get("dark_mode_prev", False):
            st.session_state.dark_mode_prev = dark_mode
            # Apply theme via session state (actual theme switching would require custom components)
        
        st.markdown("---")
        
        if st.session_state.get("authenticated", False):
            if st.button("➕ New Chat", use_container_width=True):
                start_new_chat()
            
            # Display user's conversations
            st.markdown("### Your Conversations")
            conversations = st.session_state.db.get_user_conversations(st.session_state.user_id)

            if not conversations:
                st.info("No conversations yet. Start a new chat!")
            
            for conv in conversations:
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        if st.button(f"📝 {conv[1]}", key=f"conv_{conv[0]}", use_container_width=True):
                            st.session_state.current_conversation_id = conv[0]
                            st.session_state.conversation_title = conv[1]
                            load_conversation_messages()
                    with col2:
                        if st.button("🗑️", key=f"del_{conv[0]}", help="Delete this conversation"):
                            with st.spinner("Deleting..."):
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
            
            st.markdown("---")
            
            # User profile section
            with st.expander("User Profile"):
                st.write(f"**Username:** {st.session_state.username}")
                with st.form(key="api_key_form"):
                    new_api_key = st.text_input("New Cohere API Key", type="password")
                    submit = st.form_submit_button("Update API Key")
                    if submit and new_api_key:
                        # Update API key in database
                        st.session_state.db.update_user_api_key(st.session_state.user_id, new_api_key)
                        st.session_state.api_key = new_api_key
                        st.session_state.rag_system = RAGSystem(new_api_key)
                        st.success("API Key updated successfully!")
            
            if st.button("Logout", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        else:
            st.info("Please login or register to continue.")

def load_conversation_messages():
    if st.session_state.get("current_conversation_id"):
        # Show loading state
        with st.spinner("Loading conversation..."):
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
    
    try:
        # Show loading state
        with st.spinner("Creating new chat..."):
            conversation_id = st.session_state.db.create_conversation(
                st.session_state.user_id, 
                default_title
            )
            
            # Update session state
            st.session_state.current_conversation_id = conversation_id
            st.session_state.conversation_title = default_title
            st.session_state.chat_messages = []
            st.session_state.chat_history = []
            st.session_state.messages = []  # Clear the chat UI messages
        
    except Exception as e:
        st.error(f"Failed to start new chat: {e}")
        st.exception(e)  # Show detailed error in development

def display_auth_page():
    # Load a Lottie animation for the welcome screen
    lottie_url = "https://assets10.lottiefiles.com/packages/lf20_bqyivy1b.json"  # A chat/conversation animation
    lottie_json = load_lottie_url(lottie_url)
    
    st.title("🌉 Golden Gate Ventures Knowledge Assistant")
    
    # Display Lottie animation if available, otherwise show a placeholder
    if lottie_json:
        try:
            # Import streamlit_lottie only if animation is available
            from streamlit_lottie import st_lottie
            st_lottie(lottie_json, height=200, key="welcome_animation")
        except ImportError:
            st.image("https://via.placeholder.com/400x200?text=Welcome+to+GGV+Assistant", use_column_width=True)
    else:
        st.image("https://via.placeholder.com/400x200?text=Welcome+to+GGV+Assistant", use_column_width=True)
    
    st.markdown("""
    This internal tool helps you access company knowledge and information quickly.
    Please login or register to continue.
    """)
    
    # Create tabs for login and register
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])
    
    with tab1:
        with st.form("login_form"):
            st.subheader("Login")
            username = st.text_input("Username", key="login_username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
            remember_me = st.checkbox("Remember me", key="remember_me")
            
            submitted = st.form_submit_button("Login")
            if submitted:
                if username and password:
                    with st.spinner("Logging in..."):
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
                            st.balloons()  # Celebrate successful login
                            st.rerun()
                        else:
                            st.error(result)
                else:
                    st.warning("Please enter both username and password")
    
    with tab2:
        with st.form("register_form"):
            st.subheader("Register")
            new_username = st.text_input("Username", key="reg_username", placeholder="Choose a username")
            new_email = st.text_input("Email", key="reg_email", placeholder="Enter your email")
            
            col1, col2 = st.columns(2)
            with col1:
                new_password = st.text_input("Password", type="password", key="reg_password", placeholder="Create a password")
            with col2:
                confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password", placeholder="Confirm your password")
            
            api_key = st.text_input("Cohere API Key", key="reg_api_key", 
                                placeholder="Enter your Cohere API key",
                                help="Enter your Cohere API key. This will be used for retrieving and generating responses.")
            
            terms = st.checkbox("I agree to the terms and conditions", key="terms")
            
            submitted = st.form_submit_button("Register")
            if submitted:
                if new_username and new_email and new_password and api_key and terms:
                    if new_password != confirm_password:
                        st.error("Passwords do not match")
                    else:
                        with st.spinner("Creating your account..."):
                            success, result = st.session_state.db.register_user(new_username, new_password, new_email, api_key)
                            if success:
                                st.success("Registration successful! Please login.")
                                # Switch to the login tab
                                st.experimental_set_query_params(tab="login")
                                st.rerun()
                            else:
                                st.error(result)
                else:
                    if not terms:
                        st.warning("Please agree to the terms and conditions")
                    else:
                        st.warning("Please fill all fields")

def display_chat_interface():
    # Create a header with conversation title editing
    st.title("💬 Chat Interface")
    
    # Allow user to edit conversation title
    current_title = st.session_state.get("conversation_title", "New Chat")
    
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            new_title = st.text_input(
                "Conversation Title", 
                value=current_title,
                key=f"title_input_{st.session_state.current_conversation_id}",  # Unique key based on conversation ID
                placeholder="Enter a title for this conversation"
            )
        with col2:
            update_button = st.button("Update Title", key="update_title")
        
        # Only update if title has changed and is not empty
        if update_button and new_title != current_title and new_title.strip():
            try:
                with st.spinner("Updating title..."):
                    st.session_state.db.rename_conversation(st.session_state.current_conversation_id, new_title)
                    st.session_state.conversation_title = new_title
                    # Update the sidebar without a full rerun
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to update title: {e}")
    
    # Add a separator
    st.divider()
    
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
    
    # Create a container for the chat messages with proper height
    chat_container = st.container()
    
    # Display chat messages using Streamlit's chat_message component
    with chat_container:
        if not st.session_state.messages:
            st.info("Start a conversation by typing a message below.")
        
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Add horizontal rule before the input area
    st.divider()
    
    # Chat input
    prompt = st.chat_input("Type your message...", key="chat_input")
    
    if prompt:
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
    
        # IMPORTANT: Get ALL messages for this conversation
        # Get the complete conversation history from the database
        all_messages = st.session_state.db.get_conversation_messages(st.session_state.current_conversation_id)
        st.session_state.chat_messages = all_messages
        st.session_state.chat_history = all_messages  # Use the full history
        
        # Format the chat history correctly for the RAG system
        chat_history = [(msg[0], msg[1], msg[2], msg[3]) for msg in st.session_state.chat_history]
        
        # Create a status container to display the processing status
        with st.status("Processing your question...", expanded=True) as status:
            st.write("Retrieving information...")
            
            # Get response from RAG system
            stream, sources = st.session_state.rag_system.generate_response_stream(prompt, chat_history)
            
            st.write("Generating response...")
            status.update(label="Response ready!", state="complete", expanded=False)
        
        # Display assistant response
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""
            
            # Add a progress bar for response generation
            progress_bar = st.progress(0)
            
            # Stream the response
            total_events = 0  # We don't know total events in advance
            events_processed = 0
            
            for event in stream:
                if hasattr(event, "type") and event.type == "content-delta":
                    delta_text = event.delta.message.content.text
                    full_response += delta_text
                    # Update the response in real-time
                    response_placeholder.markdown(full_response + "▌")
                    total_events += 1
                    events_processed += 1
                    # Approximate progress
                    if total_events > 0:
                        progress_bar.progress(min(events_processed / max(total_events, 10), 1.0))
                    time.sleep(0.01)  # Small delay for smoother streaming
                
                # Handle end of stream
                if hasattr(event, "type") and event.type == "message-end":
                    # Show final response without cursor
                    response_placeholder.markdown(full_response)
                    progress_bar.progress(1.0)
            
            # Remove progress bar after completion
            progress_bar.empty()
            
            # Display sources if available
            if sources and len(sources) > 0:
                with st.expander("📚 Sources", expanded=False):
                    for i, source in enumerate(sources):
                        st.markdown(f"**Source {i+1}**: {source}")
            
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
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': 'mailto:support@goldengate.ventures',
            'Report a bug': 'https://github.com/ggv/assistant/issues',
            'About': "# Golden Gate Ventures Knowledge Assistant\nThis internal tool helps team members access company knowledge quickly."
        }
    )
    
    # Apply custom CSS
    st.markdown("""
    <style>
    /* Improve chat message styling */
    div.stChatMessage {
        padding: 0.5rem 0;
    }
    
    /* Make the chat interface cleaner */
    section.main > div {
        padding-top: 1rem;
    }
    
    /* Improve form appearance */
    div.stForm > div {
        padding-top: 0.5rem;
    }
    
    /* Make buttons more prominent */
    .stButton button {
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)
    
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
