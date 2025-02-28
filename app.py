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
            
            if db_url and st.button("Connect", type="primary"):
                st.session_state.db_url = db_url
                return Database(db_url)
        
        # Return None if no URL is available yet
        return None
    
    # Return database connection with the URL
    return Database(db_url)

# Improved Streamlit UI Components
def create_sidebar():
    with st.sidebar:
        st.image("assests//company_logo.png", width=150)
        
        # Add some spacing for visual appeal
        st.markdown("---")
        st.title("Golden Gate Ventures")
        st.markdown("*Internal Knowledge Assistant*")
        
        if st.session_state.get("authenticated", False):
            st.button("✨ New Chat", on_click=start_new_chat, type="primary", use_container_width=True)
            
            st.markdown("---")
            
            # Display user's conversations with improved UI
            st.subheader("💬 Your Conversations")
            conversations = st.session_state.db.get_user_conversations(st.session_state.user_id)

            if not conversations:
                st.info("No conversations yet. Start a new chat!")
            
            for conv in conversations:
                with st.container():
                    cols = st.columns([4, 1])
                    # Make button look like a conversation entry
                    button_label = f"{conv[1]}"
                    # Truncate long conversation titles
                    if len(button_label) > 25:
                        button_label = button_label[:22] + "..."
                    
                    with cols[0]:
                        if st.button(button_label, key=f"conv_{conv[0]}", use_container_width=True):
                            st.session_state.current_conversation_id = conv[0]
                            st.session_state.conversation_title = conv[1]
                            load_conversation_messages()
                    
                    with cols[1]:
                        if st.button("🗑️", key=f"del_{conv[0]}", help="Delete conversation"):
                            # Create a confirmation message
                            if f"confirm_delete_{conv[0]}" not in st.session_state:
                                st.session_state[f"confirm_delete_{conv[0]}"] = True
                                st.warning("Confirm deletion?")
                                st.button("Yes, delete", key=f"confirm_{conv[0]}", on_click=delete_conversation, args=(conv[0],))
                                st.button("Cancel", key=f"cancel_{conv[0]}", on_click=cancel_delete, args=(conv[0],))
            
            st.markdown("---")
            # User info and logout section
            if "username" in st.session_state:
                st.caption(f"Logged in as: **{st.session_state.username}**")
            
            if st.button("🚪 Logout", type="secondary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        else:
            st.info("Please login or register to continue.")

def cancel_delete(conv_id):
    # Remove the confirmation flag
    if f"confirm_delete_{conv_id}" in st.session_state:
        del st.session_state[f"confirm_delete_{conv_id}"]

def delete_conversation(conv_id):
    st.session_state.db.delete_conversation(conv_id)
    # Reset current conversation if we're deleting the active one
    if st.session_state.current_conversation_id == conv_id:
        # Clear conversation-specific session state
        st.session_state.current_conversation_id = None
        st.session_state.conversation_title = None
        st.session_state.chat_messages = []
        st.session_state.chat_history = []
        st.session_state.messages = []
        # Start a new chat session
        start_new_chat()
    # Remove the confirmation flag
    if f"confirm_delete_{conv_id}" in st.session_state:
        del st.session_state[f"confirm_delete_{conv_id}"]
    # Force a full rerun to update the sidebar
    st.rerun()

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
    
    try:
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
        print(f"Error starting new chat: {e}")

def display_auth_page():
    # Create a nice container for the auth form
    with st.container():
        # Center the form
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("### 🌉 Welcome to Golden Gate Ventures Assistant")
            st.markdown("*Your internal knowledge base companion*")
            st.markdown("---")
            
            # Create tabs with improved styling
            tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])
            
            with tab1:
                with st.form("login_form"):
                    st.subheader("Login")
                    username = st.text_input("Username", key="login_username")
                    password = st.text_input("Password", type="password", key="login_password")
                    
                    submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
                    
                    if submitted:
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
                with st.form("register_form"):
                    st.subheader("Register")
                    new_username = st.text_input("Username", key="reg_username")
                    new_email = st.text_input("Email", key="reg_email")
                    new_password = st.text_input("Password", type="password", key="reg_password")
                    confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
                    api_key = st.text_input("Cohere API Key", key="reg_api_key", 
                                           help="Enter your Cohere API key. This will be used for retrieving and generating responses.")
                    
                    submitted = st.form_submit_button("Register", type="primary", use_container_width=True)
                    
                    if submitted:
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
    # Create a container for the chat header
    with st.container():
        cols = st.columns([3, 1])
        
        with cols[0]:
            # Allow user to edit conversation title with a nicer UI
            current_title = st.session_state.get("conversation_title", "New Chat")
            new_title = st.text_input(
                "💬 Conversation Title", 
                value=current_title,
                key=f"title_input_{st.session_state.current_conversation_id}"  # Unique key based on conversation ID
            )
            
            # Only update if title has changed and is not empty
            if new_title != current_title and new_title.strip():
                try:
                    st.session_state.db.rename_conversation(st.session_state.current_conversation_id, new_title)
                    st.session_state.conversation_title = new_title
                    # Update the sidebar without a full rerun
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update title: {e}")
    
    # Add a divider for visual separation
    st.markdown("---")
    
    # Chat container with improved styling
    chat_container = st.container()
    
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
    
    # Create a scrollable container for messages
    with chat_container:
        # Apply custom styling to messages
        if not st.session_state.messages:
            st.info("👋 Welcome! Ask me anything about Golden Gate Ventures.")
        
        # Display chat messages using Streamlit's chat_message component
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
                st.markdown(message["content"])
    
    # Chat input with custom styling
    st.markdown("---")
    prompt = st.chat_input("Type your message...", key="chat_input")
    
    if prompt:
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
    
        # Display user message immediately
        with st.chat_message("user", avatar="👤"):
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
        
        # Show typing indicator
        with st.chat_message("assistant", avatar="🤖"):
            # Add a typing indicator
            typing_placeholder = st.empty()
            typing_placeholder.markdown("*Thinking...*")
            
            # Get response from RAG system
            stream, sources = st.session_state.rag_system.generate_response_stream(prompt, chat_history)
            
            # Replace typing indicator with actual response
            response_placeholder = typing_placeholder.empty()
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
                    
                    # Show sources if available
                    if sources:
                        with st.expander("Sources"):
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

# Add custom CSS for better styling
def custom_css():
    st.markdown("""
    <style>
    /* Main app styling */
    .main {
        background-color: #f9f9f9;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #f0f2f6;
    }
    
    /* Chat container */
    .stChatMessage {
        border-radius: 15px;
        margin-bottom: 15px;
        transition: all 0.3s ease;
    }
    
    .stChatMessage:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    /* User message styling */
    .stChatMessageContent[data-testid*="user"] {
        background-color: #e6f3ff;
        border-radius: 15px;
    }
    
    /* Assistant message styling */
    .stChatMessageContent[data-testid*="assistant"] {
        background-color: #f8f9fa;
        border-radius: 15px;
    }
    
    /* Improve button styling */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Title input styling */
    .stTextInput input {
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }
    
    /* Form styling */
    .stForm {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# Main Streamlit App
def main():
    st.set_page_config(
        page_title="Golden Gate Ventures Assistant",
        page_icon="🌉",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply custom CSS
    custom_css()
    
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
