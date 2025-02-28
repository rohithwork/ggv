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

# Improved Streamlit UI Components with a modern, world-class look
def create_sidebar():
    with st.sidebar:
        st.image("assests//company_logo.png", width=150)
        st.markdown("---")
        st.title("Golden Gate Ventures")
        st.markdown("*Internal Knowledge Assistant*")
        
        if st.session_state.get("authenticated", False):
            st.button("✨ New Chat", on_click=start_new_chat, type="primary", use_container_width=True)
            st.markdown("---")
            st.subheader("💬 Your Conversations")
            conversations = st.session_state.db.get_user_conversations(st.session_state.user_id)

            if not conversations:
                st.info("No conversations yet. Start a new chat!")
            
            for conv in conversations:
                with st.container():
                    cols = st.columns([4, 1])
                    # Truncate long conversation titles
                    button_label = conv[1] if len(conv[1]) <= 25 else conv[1][:22] + "..."
                    
                    with cols[0]:
                        if st.button(button_label, key=f"conv_{conv[0]}", use_container_width=True):
                            st.session_state.current_conversation_id = conv[0]
                            st.session_state.conversation_title = conv[1]
                            load_conversation_messages()
                    
                    with cols[1]:
                        if st.button("🗑️", key=f"del_{conv[0]}", help="Delete conversation"):
                            if f"confirm_delete_{conv[0]}" not in st.session_state:
                                st.session_state[f"confirm_delete_{conv[0]}"] = True
                                st.warning("Confirm deletion?")
                                st.button("Yes, delete", key=f"confirm_{conv[0]}", on_click=delete_conversation, args=(conv[0],))
                                st.button("Cancel", key=f"cancel_{conv[0]}", on_click=cancel_delete, args=(conv[0],))
            
            st.markdown("---")
            if "username" in st.session_state:
                st.caption(f"Logged in as: **{st.session_state.username}**")
            if st.button("🚪 Logout", type="secondary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        else:
            st.info("Please login or register to continue.")

def cancel_delete(conv_id):
    if f"confirm_delete_{conv_id}" in st.session_state:
        del st.session_state[f"confirm_delete_{conv_id}"]

def delete_conversation(conv_id):
    st.session_state.db.delete_conversation(conv_id)
    if st.session_state.current_conversation_id == conv_id:
        st.session_state.current_conversation_id = None
        st.session_state.conversation_title = None
        st.session_state.chat_messages = []
        st.session_state.chat_history = []
        st.session_state.messages = []
        start_new_chat()
    if f"confirm_delete_{conv_id}" in st.session_state:
        del st.session_state[f"confirm_delete_{conv_id}"]
    st.rerun()

def load_conversation_messages():
    if st.session_state.get("current_conversation_id"):
        messages = st.session_state.db.get_conversation_messages(st.session_state.current_conversation_id)
        st.session_state.chat_messages = messages
        st.session_state.chat_history = messages
        st.session_state.messages = []
        for msg in messages:
            role = "user" if msg[1] else "assistant"
            st.session_state.messages.append({"role": role, "content": msg[2]})

def start_new_chat():
    default_title = f"New chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    try:
        conversation_id = st.session_state.db.create_conversation(
            st.session_state.user_id, 
            default_title
        )
        st.session_state.current_conversation_id = conversation_id
        st.session_state.conversation_title = default_title
        st.session_state.chat_messages = []
        st.session_state.chat_history = []
        st.session_state.messages = []
    except Exception as e:
        st.error(f"Failed to start new chat: {e}")
        print(f"Error starting new chat: {e}")

def display_auth_page():
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🌉 Welcome to Golden Gate Ventures Assistant")
            st.markdown("*Your internal knowledge base companion*")
            st.markdown("---")
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
                                api_key = st.session_state.db.get_user_api_key(result)
                                st.session_state.api_key = api_key
                                st.session_state.rag_system = RAGSystem(api_key)
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
                                    st.rerun()
                                else:
                                    st.error(result)
                        else:
                            st.warning("Please fill all fields")

def display_chat_interface():
    with st.container():
        cols = st.columns([3, 1])
        with cols[0]:
            current_title = st.session_state.get("conversation_title", "New Chat")
            new_title = st.text_input(
                "💬 Conversation Title", 
                value=current_title,
                key=f"title_input_{st.session_state.current_conversation_id}"
            )
            if new_title != current_title and new_title.strip():
                try:
                    st.session_state.db.rename_conversation(st.session_state.current_conversation_id, new_title)
                    st.session_state.conversation_title = new_title
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update title: {e}")
    st.markdown("---")
    chat_container = st.container()
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        if "chat_messages" in st.session_state and st.session_state.chat_messages:
            for msg in st.session_state.chat_messages:
                role = "user" if msg[1] else "assistant"
                st.session_state.messages.append({"role": role, "content": msg[2]})
    
    with chat_container:
        if not st.session_state.messages:
            st.info("👋 Welcome! Ask me anything about Golden Gate Ventures.")
        for message in st.session_state.messages:
            with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
                st.markdown(message["content"])
    
    st.markdown("---")
    prompt = st.chat_input("Type your message...", key="chat_input")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        st.session_state.db.add_message(
            st.session_state.current_conversation_id,
            st.session_state.user_id,
            True,
            prompt
        )
        all_messages = st.session_state.db.get_conversation_messages(st.session_state.current_conversation_id)
        st.session_state.chat_messages = all_messages
        st.session_state.chat_history = all_messages
        chat_history = [(msg[0], msg[1], msg[2], msg[3]) for msg in st.session_state.chat_history]
        
        with st.chat_message("assistant", avatar="🤖"):
            typing_placeholder = st.empty()
            typing_placeholder.markdown("*Thinking...*")
            stream, sources = st.session_state.rag_system.generate_response_stream(prompt, chat_history)
            response_placeholder = typing_placeholder.empty()
            full_response = ""
            for event in stream:
                if hasattr(event, "type") and event.type == "content-delta":
                    delta_text = event.delta.message.content.text
                    full_response += delta_text
                    response_placeholder.markdown(full_response + "▌")
                    time.sleep(0.01)
                if hasattr(event, "type") and event.type == "message-end":
                    response_placeholder.markdown(full_response)
                    if sources:
                        with st.expander("Sources"):
                            for i, source in enumerate(sources):
                                st.markdown(f"**Source {i+1}**: {source}")
            st.session_state.db.add_message(
                st.session_state.current_conversation_id,
                st.session_state.user_id,
                False,
                full_response
            )
            st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.session_state.chat_messages.append((str(uuid.uuid4()), True, prompt, datetime.now()))
        st.session_state.chat_messages.append((str(uuid.uuid4()), False, full_response, datetime.now()))

def custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Roboto', sans-serif;
    }

    /* Main app styling */
    .main {
        background-color: var(--background-color);
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: var(--sidebar-bg);
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
        background-color: rgba(53, 130, 220, 0.2);
        border-radius: 15px;
    }
    
    /* Assistant message styling */
    .stChatMessageContent[data-testid*="assistant"] {
        background-color: rgba(240, 242, 246, 0.1);
        border-radius: 15px;
    }
    
    /* Button styling */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Input styling */
    .stTextInput input {
        border-radius: 8px;
        border: 1px solid var(--input-border);
        color: var(--text-color) !important;
        background-color: var(--input-bg) !important;
    }
    
    /* Form styling */
    .stForm {
        background-color: var(--form-bg);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    .stForm label {
        color: var(--text-color) !important;
    }
    
    :root {
        --text-color: #31333F;
        --background-color: #f9f9f9;
        --sidebar-bg: #f0f2f6;
        --input-border: #e0e0e0;
        --input-bg: #ffffff;
        --form-bg: #ffffff;
    }
    
    @media (prefers-color-scheme: dark) {
        :root {
            --text-color: #fafafa;
            --background-color: #0e1117;
            --sidebar-bg: #1e1e1e;
            --input-border: #4a4a4a;
            --input-bg: #262730;
            --form-bg: #262730;
        }
    }
    
    [data-theme="dark"] input, 
    [data-theme="dark"] .stTextInput input {
        color: var(--text-color) !important;
    }
    
    [data-theme="dark"] .stForm label span,
    [data-theme="dark"] .stTextInput label span,
    [data-theme="dark"] .stTextInput span p,
    [data-theme="dark"] .stForm span p {
        color: var(--text-color) !important;
        opacity: 1 !important;
    }
    
    [data-theme="dark"] input::placeholder {
        color: rgba(250, 250, 250, 0.6) !important;
    }
    
    [data-theme="dark"] .stTabs [data-baseweb="tab-list"] button {
        color: var(--text-color) !important;
    }
    
    [data-theme="dark"] .streamlit-expanderHeader {
        color: var(--text-color) !important;
    }
    </style>
    """, unsafe_allow_html=True)

def main():
    st.set_page_config(
        page_title="Golden Gate Ventures Assistant",
        page_icon="🌉",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    custom_css()
    
    if "db" not in st.session_state:
        st.session_state.db = get_db_connection()
        if st.session_state.db is None:
            st.warning("Please configure your Neon database connection to continue")
            return
    
    create_sidebar()
    
    if st.session_state.get("authenticated", False):
        if "current_conversation_id" not in st.session_state:
            start_new_chat()
        display_chat_interface()
    else:
        display_auth_page()

if __name__ == "__main__":
    main()
