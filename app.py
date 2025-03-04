import streamlit as st
import time
import os
from datetime import datetime
import uuid
import pinecone
from pinecone import ServerlessSpec, Pinecone 
import re

# Import custom modules
from database import Database
from rag_system import RAGSystem
from chunking import parse_markdown, chunk_content
from embedding import generate_and_store_embeddings

import re

import re
import pinecone
import streamlit as st

import re
from pinecone import Pinecone
import streamlit as st

def initialize_pinecone(api_key, environment, index_name, dimension=768):
    try:
        # Validate the index name using a regular expression
        if not re.match(r'^[a-z0-9\-]+$', index_name):
            st.error("Invalid index name. It must consist of lowercase alphanumeric characters or hyphens (-).")
            return None
        
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key)
        
        # Check if the index exists
        index_list = [index.name for index in pc.list_indexes()]
        if index_name in index_list:
            st.info(f"Pinecone index '{index_name}' already exists.")
            
            # Ask the user what to do
            action = st.selectbox(
                "What would you like to do?",
                ["Use Existing Index", "Delete and Create New Index"],
                key="index_action"
            )
            
            if action == "Delete and Create New Index":
                # Delete the existing index
                pc.delete_index(index_name)
                st.success(f"Deleted existing Pinecone index '{index_name}'.")
                
                # Create a new index
                pc.create_index(
                    name=index_name,
                    dimension=dimension,  # Adjust based on your embedding model
                    metric='cosine',
                    spec=ServerlessSpec(cloud='aws', region=environment)
                )
                st.success(f"Created new Pinecone index '{index_name}'.")
            else:
                st.info(f"Using existing Pinecone index '{index_name}'.")
        else:
            # Create the index if it doesn't exist
            pc.create_index(
                name=index_name,
                dimension=dimension,  # Adjust based on your embedding model
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region=environment)
            )
            st.success(f"Pinecone index '{index_name}' created successfully.")
        
        # Return the Pinecone index object
        return pc.Index(index_name)
    
    except Exception as e:
        st.error(f"Unexpected error initializing Pinecone: {str(e)}")
        return None

def select_pinecone_index():
    """Allow users to select or disconnect from a Pinecone index"""
    st.subheader("Pinecone Index Management")
    
    # Check if an index is already connected
    if "pinecone_index_name" in st.session_state:
        st.success(f"Connected to Pinecone index: {st.session_state.pinecone_index_name}")
        
        # Add a disconnect button
        if st.button("Disconnect from Index", type="secondary"):
            del st.session_state.pinecone_index_name
            del st.session_state.rag_system
            st.success("Disconnected from Pinecone index.")
            st.rerun()
        return
    
    # Get the user's Pinecone API key from the database
    pinecone_api_key = st.session_state.db.get_pinecone_api_key(st.session_state.user_id)
    if not pinecone_api_key:
        st.error("Pinecone API key not found for your account. Please contact an administrator.")
        return
    
    # Initialize Pinecone client
    try:
        pc = Pinecone(api_key=pinecone_api_key)
    except Exception as e:
        st.error(f"Failed to connect to Pinecone: {str(e)}")
        return
    
    # List available indexes
    index_list = [index.name for index in pc.list_indexes()]
    
    if not index_list:
        st.error("No Pinecone indexes found. Please contact an administrator.")
        return
    
    # Dropdown to select an index
    selected_index = st.selectbox("Select an Index", index_list)
    
    if st.button("Connect to Index", type="primary"):
        st.session_state.pinecone_index_name = selected_index
        st.success(f"Connected to Pinecone index: {selected_index}")
        
        # Reinitialize RAGSystem with the selected index
        user_details = st.session_state.db.get_user_details(st.session_state.user_id)
        st.session_state.rag_system = RAGSystem(
            api_key=user_details["api_key"],
            pinecone_api_key=pinecone_api_key,
            pinecone_environment="us-east-1",  # Replace with your Pinecone environment
            index_name=selected_index
        )
        st.rerun()

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
            # If user is admin, show admin controls
            if st.session_state.get("is_admin", False):
                # Toggle between admin view and chat view
                if st.session_state.get("admin_view", False):
                    st.button("💬 Chat View", on_click=toggle_admin_view, type="primary", use_container_width=True)
                else:
                    st.button("🔧 Admin Dashboard", on_click=toggle_admin_view, type="primary", use_container_width=True)
                    st.button("✨ New Chat", on_click=start_new_chat, type="secondary", use_container_width=True)
            else:
                # Regular user only sees new chat button
                st.button("✨ New Chat", on_click=start_new_chat, type="primary", use_container_width=True)
            
            st.markdown("---")
            
            # Only show conversation list in chat view
            if not st.session_state.get("admin_view", False):
                # Display user's conversations with improved UI
                st.subheader("💬 Your Conversations")
                # Regular users see their own conversations, admins see all if in admin view
                is_admin_view = st.session_state.get("is_admin", False) and st.session_state.get("admin_view", False)
                conversations = st.session_state.db.get_user_conversations(
                    st.session_state.user_id, 
                    is_admin=is_admin_view
                )

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
                                st.session_state.viewing_as_admin = False
                                load_conversation_messages()
                        
                        with cols[1]:
                            if st.button("🗑️", key=f"del_{conv[0]}", help="Delete conversation"):
                                # Delete conversation immediately without confirmation
                                delete_conversation(conv[0])
            
            st.markdown("---")
            # User info and logout section
            if "email" in st.session_state:
                user_type = "Admin" if st.session_state.get("is_admin", False) else "User"
                st.caption(f"Logged in as: **{st.session_state.email}** ({user_type})")
            
            if st.button("🚪 Logout", type="secondary", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        else:
            st.info("Please login to continue.")

def toggle_admin_view():
    """Toggle between admin view and chat view"""
    st.session_state.admin_view = not st.session_state.get("admin_view", False)

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
    # Force a full rerun to update the sidebar
    st.rerun()

def load_conversation_messages():
    if st.session_state.get("current_conversation_id"):
        # Check if user has permission to access this conversation
        if not st.session_state.db.can_access_conversation(
            st.session_state.user_id, 
            st.session_state.current_conversation_id
        ):
            st.error("You don't have permission to access this conversation")
            start_new_chat()
            st.rerun()
            return
            
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

# Modified display_auth_page() function
def display_auth_page():
    """Display the login page"""
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("### 🌉 Welcome to Golden Gate Ventures Assistant")
            st.markdown("*Your internal knowledge base companion*")
            st.markdown("---")
            
            # Login form with admin checkbox
            with st.form("login_form"):
                st.subheader("Login")
                email = st.text_input("Email", key="login_email")
                is_admin_login = st.checkbox("I am an admin", key="is_admin_login")
                
                password = None
                if is_admin_login:
                    password = st.text_input("Password", type="password", key="login_password")
                
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
                
                if submitted:
                    if not email:
                        st.warning("Please enter your email")
                    elif is_admin_login and not password:
                        st.warning("Admin login requires a password")
                    else:
                        if not is_admin_login:
                            # Non-admin login (no password required)
                            success, result = st.session_state.db.login_user_without_password(email)
                            if not success:
                                st.error(result)
                            elif result.get("is_admin", False):
                                st.error("This account has admin privileges. Please log in as an admin.")
                            else:
                                # Non-admin login successful
                                st.session_state.authenticated = True
                                st.session_state.user_id = result["user_id"]
                                st.session_state.is_admin = False
                                st.session_state.email = email
                                
                                # Redirect to index selection
                                st.rerun()
                        else:
                            # Admin login with password verification
                            success, result = st.session_state.db.login_user(email, password)
                            if success:
                                if not result.get("is_admin", False):
                                    st.error("This account does not have admin privileges")
                                else:
                                    st.session_state.authenticated = True
                                    st.session_state.user_id = result["user_id"]
                                    st.session_state.is_admin = result["is_admin"]
                                    st.session_state.email = email
                                    
                                    # Redirect to index selection
                                    st.rerun()
                            else:
                                st.error(result)
            
            st.info("If you don't have an account, please contact an administrator.")
def display_admin_page():
    """Display the admin dashboard with comprehensive management tools"""
    st.title("🔧 Admin Dashboard")
    
    # Create tabs for different admin functions
    admin_tabs = st.tabs([
        "👥 User Management", 
        "🔑 API Key Management", 
        "📚 Knowledge Base", 
        "💬 Conversation Management"
    ])
    
    # User Management Tab
    with admin_tabs[0]:
        st.subheader("Manage Users")
        
        # User Registration Section
        with st.form("add_user_form", clear_on_submit=True):
            st.subheader("Register New User")
            col1, col2 = st.columns(2)
            
            with col1:
                new_email = st.text_input("Email Address", placeholder="user@company.com")
                api_key = st.text_input("Cohere API Key", type="password")
            
            with col2:
                pinecone_api_key = st.text_input("Pinecone API Key", type="password")
                is_admin = st.checkbox("Grant Admin Privileges")
            
            submit_user = st.form_submit_button("Add User", type="primary")
            
            if submit_user:
                # Validation checks
                if not new_email or not api_key or not pinecone_api_key:
                    st.warning("All fields are required")
                else:
                    try:
                        success, result = st.session_state.db.register_user(
                            new_email, 
                            "no_password_required", 
                            api_key, 
                            pinecone_api_key, 
                            is_admin
                        )
                        
                        if success:
                            st.success(f"User {new_email} registered successfully")
                        else:
                            st.error(result)
                    except Exception as e:
                        st.error(f"Registration failed: {str(e)}")
        
        # Existing Users Section
        st.subheader("Existing Users")
        try:
            users = st.session_state.db.get_all_users()
            
            if users:
                # Convert users to DataFrame for better display
                import pandas as pd
                user_data = []
                for user in users:
                    user_id, email, is_admin, created_at, last_login = user
                    user_data.append({
                        "User ID": user_id,
                        "Email": email,
                        "Admin": "✅" if is_admin else "❌",
                        "Created": created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A",
                        "Last Login": last_login.strftime("%Y-%m-%d %H:%M") if last_login else "Never"
                    })
                
                df = pd.DataFrame(user_data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No users found")
        
        except Exception as e:
            st.error(f"Error retrieving users: {str(e)}")
    
    # API Key Management Tab
    with admin_tabs[1]:
        st.subheader("Manage API Keys")
        
        # Cohere API Key Management
        st.markdown("#### Cohere API Key")
        user_emails = [user[1] for user in st.session_state.db.get_all_users()]
        selected_email = st.selectbox("Select User", user_emails)
        
        if selected_email:
            user_id = [user[0] for user in st.session_state.db.get_all_users() if user[1] == selected_email][0]
            
            with st.form("update_cohere_key", clear_on_submit=True):
                new_cohere_key = st.text_input("New Cohere API Key", type="password")
                submit_cohere_key = st.form_submit_button("Update Cohere Key")
                
                if submit_cohere_key:
                    try:
                        success, message = st.session_state.db.update_cohere_api_key(
                            user_id, 
                            new_cohere_key, 
                            st.session_state.user_id
                        )
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    except Exception as e:
                        st.error(f"Update failed: {str(e)}")
        
        # Pinecone API Key Management
        st.markdown("---")
        st.markdown("#### Pinecone API Key")
        pinecone_selected_email = st.selectbox("Select User for Pinecone", user_emails)
        
        if pinecone_selected_email:
            pinecone_user_id = [user[0] for user in st.session_state.db.get_all_users() if user[1] == pinecone_selected_email][0]
            
            with st.form("update_pinecone_key", clear_on_submit=True):
                new_pinecone_key = st.text_input("New Pinecone API Key", type="password")
                submit_pinecone_key = st.form_submit_button("Update Pinecone Key")
                
                if submit_pinecone_key:
                    try:
                        success, message = st.session_state.db.update_pinecone_api_key(
                            pinecone_user_id, 
                            new_pinecone_key, 
                            st.session_state.user_id
                        )
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    except Exception as e:
                        st.error(f"Update failed: {str(e)}")
    
    # Knowledge Base Management Tab
    with admin_tabs[2]:
        st.subheader("Knowledge Base Management")
        
        # Pinecone Configuration
        st.markdown("#### Pinecone Index Configuration")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pinecone_api_key = st.text_input("Pinecone API Key", type="password")
        
        with col2:
            pinecone_environment = st.text_input("Environment", placeholder="us-east-1")
        
        with col3:
            index_name = st.text_input("Index Name", placeholder="my-knowledge-base")
        
        # File Upload Section
        st.markdown("#### Upload Knowledge Base")
        uploaded_file = st.file_uploader("Upload Markdown (.md) File", type=["md"])
        
        if uploaded_file:
            # Progress tracking containers
            progress_container = st.container()
            with progress_container:
                # Overall progress bar
                progress_bar = st.progress(0, text="Preparing file upload...")
                
                # Batch processing status
                batch_status = st.empty()
                batch_details = st.empty()
            
            try:
                # Read and process file
                md_text = uploaded_file.read().decode("utf-8")
                
                if len(md_text.strip()) == 0:
                    raise ValueError("The uploaded file is empty.")
                
                # Parse markdown
                parsed_data = parse_markdown(md_text)
                
                # Chunk content
                chunks = chunk_content(parsed_data, max_tokens=500)
                
                if not chunks:
                    raise ValueError("No valid content chunks could be generated.")
                
                # Pinecone embedding configuration
                if pinecone_api_key and pinecone_environment and index_name:
                    # Initialize Pinecone
                    pc = Pinecone(api_key=pinecone_api_key)
                    
                    # Create or use existing index
                    if index_name not in [index.name for index in pc.list_indexes()]:
                        pc.create_index(
                            name=index_name,
                            dimension=768,  # Adjust based on embedding model
                            metric='cosine',
                            spec=ServerlessSpec(cloud='aws', region=pinecone_environment)
                        )
                    
                    index = pc.Index(index_name)
                    
                    # Detailed progress callback
                    def progress_callback(current_batch, total_batches, batch_size, batch_progress):
                        # Calculate overall progress percentage
                        progress_percentage = int((batch_progress['processed_chunks'] / batch_progress['total_chunks']) * 100)
                        
                        # Update progress bar
                        progress_bar.progress(
                            progress_percentage, 
                            text=f"Processing Embeddings: {batch_progress['processed_chunks']}/{batch_progress['total_chunks']} chunks"
                        )
                        
                        # Update batch status
                        batch_status.markdown(f"**Batch {current_batch}/{total_batches}**")
                        batch_details.caption(
                            f"Processing batch of {batch_size} chunks. "
                            f"Total chunks processed: {batch_progress['processed_chunks']}"
                        )
                    
                    # Spinner with embedding generation
                    with st.spinner("Generating semantic embeddings..."):
                        embedding_stats = generate_and_store_embeddings(
                            chunks, 
                            index, 
                            progress_callback=progress_callback
                        )
                    
                    # Final success message
                    st.success(
                        f"Upload complete! "
                        f"Processed {embedding_stats['total_chunks']} chunks "
                        f"in {embedding_stats['total_batches']} batches."
                    )
                
                else:
                    raise ValueError("Invalid Pinecone configuration")
            
            except Exception as e:
                st.error(f"Upload failed: {str(e)}")
        
        # Reset Index Option
        st.markdown("#### Reset Pinecone Index")
        reset_col1, reset_col2 = st.columns([3, 1])
        
        with reset_col1:
            st.warning("Resetting the index will delete all existing vectors")
        
        with reset_col2:
            if st.button("Reset Index", type="primary"):
                try:
                    pc = Pinecone(api_key=pinecone_api_key)
                    if index_name in [index.name for index in pc.list_indexes()]:
                        pc.delete_index(index_name)
                        st.success(f"Index {index_name} deleted successfully")
                except Exception as e:
                    st.error(f"Reset failed: {str(e)}")
    
    # Conversation Management Tab
    with admin_tabs[3]:
        st.subheader("All Conversations")
        
        try:
            # Fetch all conversations
            conversations = st.session_state.db.get_user_conversations(
                st.session_state.user_id, 
                is_admin=True
            )
            
            if conversations:
                # Convert to DataFrame for better display
                import pandas as pd
                conv_data = []
                for conv in conversations:
                    conv_id, title, created_at, user_email = conv
                    conv_data.append({
                        "Conversation ID": conv_id,
                        "Title": title,
                        "User": user_email,
                        "Created": created_at.strftime("%Y-%m-%d %H:%M")
                    })
                
                df = pd.DataFrame(conv_data)
                st.dataframe(df, use_container_width=True)
                
                # Bulk delete option
                if st.checkbox("Select Conversations to Delete"):
                    selected_convs = st.multiselect("Choose Conversations", df["Conversation ID"])
                    
                    if st.button("Delete Selected Conversations"):
                        for conv_id in selected_convs:
                            st.session_state.db.delete_conversation(conv_id)
                        st.success(f"Deleted {len(selected_convs)} conversations")
            else:
                st.info("No conversations found")
        
        except Exception as e:
            st.error(f"Error retrieving conversations: {str(e)}")
def display_chat_interface():
    """Display the chat interface"""
    # Check if an index has been selected
    if "pinecone_index_name" not in st.session_state:
        st.warning("Please select a Pinecone index to proceed.")
        select_pinecone_index()
        return
    
    # Rest of the chat interface remains unchanged
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
                is_user = msg[1]
                content = msg[2]
                role = "user" if is_user else "assistant"
                st.session_state.messages.append({"role": role, "content": content})
    
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
            True,  # is_user
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
                False,  # is_user
                full_response
            )
            st.session_state.messages.append({"role": "assistant", "content": full_response})
        
        st.session_state.chat_messages.append((str(uuid.uuid4()), True, prompt, datetime.now()))
        st.session_state.chat_messages.append((str(uuid.uuid4()), False, full_response, datetime.now()))
def custom_css():
    st.markdown("""
    <style>
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
    
    /* User message styling - works in both light and dark mode */
    .stChatMessageContent[data-testid*="user"] {
        background-color: rgba(53, 130, 220, 0.2);
        border-radius: 15px;
    }
    
    /* Assistant message styling - works in both light and dark mode */
    .stChatMessageContent[data-testid*="assistant"] {
        background-color: rgba(240, 242, 246, 0.1);
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
    
    /* Title input styling - ensure text is visible in dark mode */
    .stTextInput input {
        border-radius: 8px;
        border: 1px solid var(--input-border);
        color: var(--text-color) !important;
        background-color: var(--input-bg) !important;
    }
    
    /* Form styling - ensure text is visible in dark mode */
    .stForm {
        background-color: var(--form-bg);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    /* Fix form labels for dark mode */
    .stForm label {
        color: var(--text-color) !important;
    }
    
    /* CSS variables for theme compatibility */
    :root {
        --text-color: #31333F;
        --background-color: #f9f9f9;
        --sidebar-bg: #f0f2f6;
        --input-border: #e0e0e0;
        --input-bg: #ffffff;
        --form-bg: #ffffff;
    }
    
    /* Dark mode specific variables */
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
    
    /* Override Streamlit's dark mode text for inputs */
    [data-theme="dark"] input, 
    [data-theme="dark"] .stTextInput input {
        color: var(--text-color) !important;
    }
    
    /* Additional fix for form elements in dark mode */
    [data-theme="dark"] .stForm label span,
    [data-theme="dark"] .stTextInput label span,
    [data-theme="dark"] .stTextInput span p,
    [data-theme="dark"] .stForm span p {
        color: var(--text-color) !important;
        opacity: 1 !important;
    }
    
    /* Fix text input placeholder color in dark mode */
    [data-theme="dark"] input::placeholder {
        color: rgba(250, 250, 250, 0.6) !important;
    }
    
    /* Ensure tab labels are visible in dark mode */
    [data-theme="dark"] .stTabs [data-baseweb="tab-list"] button {
        color: var(--text-color) !important;
    }
    
    /* Fix expander text color in dark mode */
    [data-theme="dark"] .streamlit-expanderHeader {
        color: var(--text-color) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# You may also need to update init_db in main() function
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
        try:
            st.session_state.db = get_db_connection()
            
            # If no database connection is available yet, show only the database configuration UI
            if st.session_state.db is None:
                st.warning("Please configure your Neon database connection to continue")
                return
        except Exception as e:
            st.error(f"Database connection error: {str(e)}")
            return
    
    # Create sidebar
    create_sidebar()
    
    # Main content
    if st.session_state.get("authenticated", False):
        # Check if we should show admin view for admin users
        if st.session_state.get("is_admin", False) and st.session_state.get("admin_view", False):
            display_admin_page()
        else:
            # Regular chat interface
            if "current_conversation_id" not in st.session_state:
                start_new_chat()
            
            # Display chat interface
            display_chat_interface()
    else:
        display_auth_page()

if __name__ == "__main__":
    main()
