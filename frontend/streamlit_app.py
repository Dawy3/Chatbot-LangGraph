import streamlit as st
import requests
import uuid
import os

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

st.set_page_config(page_title="LangGraph Chatbot", page_icon="🤖")
st.title("🤖 OpenRouter LangGraph Chatbot")

# Initialize Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for controls
with st.sidebar:
    st.header("Debug Info")
    st.text(f"Session ID:\n{st.session_state.session_id}")
    if st.button("Clear Conversation"):
        try:
            requests.delete(f"{BACKEND_URL}/conversations/{st.session_state.session_id}")
            st.session_state.messages = []
            st.rerun()
        except Exception as e:
            st.error(f"Failed to clear: {e}")

# Load History (only once on first load)
if not st.session_state.get("history_loaded", False):
    try:
        res = requests.get(f"{BACKEND_URL}/conversations/{st.session_state.session_id}/history")
        if res.status_code == 200:
            data = res.json()
            st.session_state.messages = data.get("messages", [])
            st.session_state.history_loaded = True
    except Exception:
        st.warning("Could not connect to backend.")

# Display Chat Messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("What is up?"):
    # 1. Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Call Backend
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # We use the REST endpoint here for simplicity, 
            # but you could use the WebSocket endpoint for token streaming.
            payload = {
                "message": prompt,
                "session_id": st.session_state.session_id
            }
            
            response = requests.post(f"{BACKEND_URL}/chat", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                full_response = data["response"]
                message_placeholder.markdown(full_response)
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            else:
                st.error(f"Error: {response.status_code}")
                
        except Exception as e:
            st.error(f"Connection failed: {e}")