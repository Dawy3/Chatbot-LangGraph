import streamlit as st
import asyncio
import websockets
import json
import uuid
import os
from datetime import datetime
from typing import List, Dict, Any

# --- Configuration ---
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "ws://localhost:8000/ws/chat")

# --- Initialize Session State ---
if "sessions" not in st.session_state:
    st.session_state.sessions = {}
    
if "current_session_id" not in st.session_state:
    session_id = str(uuid.uuid4())
    st.session_state.current_session_id = session_id
    st.session_state.sessions[session_id] = {
        "messages": [],
        "title": "New Conversation",
        "created_at": datetime.now().isoformat()
    }

# --- Helper Functions ---
async def send_message_websocket(session_id: str, message: str, placeholder):
    """
    Connect to WebSocket and stream the response.
    """
    uri = f"{WEBSOCKET_URL}/{session_id}"
    full_response = ""
    is_first_token = True
    
    try:
        async with websockets.connect(uri, ping_timeout=60, close_timeout=10) as websocket:
            # Send user message
            payload = json.dumps({"message": message})
            await websocket.send(payload)
            
            # Show thinking indicator initially
            placeholder.markdown("🤔 *Thinking...*")
            
            # Receive streaming response
            while True:
                try:
                    response = await websocket.recv()
                    data = json.loads(response)
                    
                    if data.get("type") == "token":
                        content = data.get("content", "")
                        
                        # Clear thinking indicator on first real token
                        if is_first_token and content.strip():
                            is_first_token = False
                        
                        full_response += content
                        placeholder.markdown(full_response + "▌")
                        
                    elif data.get("type") == "complete":
                        placeholder.markdown(full_response)
                        break
                        
                except websockets.exceptions.ConnectionClosed:
                    break
                    
        return full_response
        
    except websockets.exceptions.InvalidStatusCode as e:
        error_msg = f"WebSocket connection failed with status {e.status_code}"
        st.error(f"{error_msg}\n\nURL: {uri}\n\nMake sure the backend is running!")
        return None
    except ConnectionRefusedError:
        st.error(f"Cannot connect to backend at {uri}\n\nIs the backend server running?")
        return None
    except Exception as e:
        st.error(f"WebSocket error: {str(e)}\n\nConnection URL: {uri}")
        return None

def create_new_session():
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    st.session_state.sessions[session_id] = {
        "messages": [],
        "title": "New Conversation",
        "created_at": datetime.now().isoformat()
    }
    st.session_state.current_session_id = session_id
    st.rerun()

def switch_session(session_id: str):
    """Switch to a different session."""
    st.session_state.current_session_id = session_id
    st.rerun()

def delete_session(session_id: str):
    """Delete a session."""
    if session_id in st.session_state.sessions:
        del st.session_state.sessions[session_id]
        
    if st.session_state.current_session_id == session_id:
        create_new_session()
    else:
        st.rerun()

def update_session_title(session_id: str, first_message: str):
    """Update session title based on first message."""
    if st.session_state.sessions[session_id]["title"] == "New Conversation":
        title = first_message[:50] + "..." if len(first_message) > 50 else first_message
        st.session_state.sessions[session_id]["title"] = title

# --- Sidebar ---
with st.sidebar:
    st.title("💬 Chat Sessions")
    
    # Connection status indicator
    st.caption(f"🔌 Backend: {WEBSOCKET_URL}")
    
    if st.button("➕ New Chat", use_container_width=True):
        create_new_session()
    
    st.divider()
    
    sessions_sorted = sorted(
        st.session_state.sessions.items(),
        key=lambda x: x[1]["created_at"],
        reverse=True
    )
    
    for session_id, session_data in sessions_sorted:
        col1, col2 = st.columns([4, 1])
        
        with col1:
            is_current = session_id == st.session_state.current_session_id
            button_label = f"{'🟢 ' if is_current else ''}{session_data['title']}"
            
            if st.button(
                button_label,
                key=f"session_{session_id}",
                use_container_width=True,
                disabled=is_current
            ):
                switch_session(session_id)
        
        with col2:
            if st.button("🗑️", key=f"delete_{session_id}"):
                delete_session(session_id)
    
    st.divider()
    st.caption(f"Total Sessions: {len(st.session_state.sessions)}")

# --- Main Chat Interface ---
st.title("🤖 LangGraph Chatbot")

current_session = st.session_state.sessions[st.session_state.current_session_id]

# Display chat messages
chat_container = st.container()
with chat_container:
    for msg in current_session["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Type your message here..."):
    current_session["messages"].append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now().isoformat()
    })
    
    if len(current_session["messages"]) == 1:
        update_session_title(st.session_state.current_session_id, prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        response = asyncio.run(
            send_message_websocket(
                st.session_state.current_session_id,
                prompt,
                message_placeholder
            )
        )
        
        if response:
            current_session["messages"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now().isoformat()
            })

# Footer
st.divider()
st.caption("Powered by LangGraph + OpenRouter + Streamlit")