import os 
import json 
import logging
from contextlib import asynccontextmanager
from typing import Annotated, TypedDict, Sequence, List, Dict, Any
from datetime import datetime

import asyncpg 
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel


# LangChain / LangGraph Imports
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


from dotenv import load_dotenv
load_dotenv()

# --- Configuration ---
# 1. Database configuration
DATABASE_URL = os.getenv("DATABASE_URL") 

# 2.Openrouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_NAME = os.getenv("MODEL_NAME")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models --- 
class ChatRequest(BaseModel):
    message : str
    session_id : str

class ChatResponse(BaseModel):
    response : str
    session_id : str
    
class MessageDto(BaseModel):
    role : str
    content : str
    timestamp : str
    
class HistoryResponse(BaseModel):
    session_id : str
    messages: List[MessageDto]
    
# --- State Definition ---
class AgentState(TypedDict):
    # 'add_messages' handles deduplication and appending automatically
    messages: Annotated[Sequence[BaseMessage], add_messages]

# --- Graph Construction ---
def build_graph():
    """Build The LangGraph Structure (Nodes and Edge)"""
    
    # 1. Initialize Model
    llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL,
        temperature=0.7,
        streaming=True)
    
    # 2. Define Logic
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are helpful AI assistant. Answer concisely."),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    chain = prompt | llm
    
    async def call_model(state: AgentState):
        response = await chain.ainvoke(state)
        return {"messages": [response]}
    
    # 3. Define Graph
    workflow = StateGraph(AgentState)
    workflow.add_node("chatbot", call_model)
    workflow.add_edge(START, "chatbot")
    workflow.add_edge("chatbot", END)
    
    return workflow
    
# --- FastAPI Lifespan (connection Management) ---
@asynccontextmanager
async def lifespan(app:FastAPI):
    """
    Manages the lifecycle of the Postgres connection pool and checkpointer.
    """
    logger.info("Starting up: Connecting to Database...")
    
    # Initialize checkpointer directly with connection string
    # AsyncPostgresSaver will manage its own connection pool internally
    checkpointer = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
    
    # Enter the context manager and keep it open for the app lifetime
    checkpointer_ctx = checkpointer.__aenter__()
    checkpointer_instance = await checkpointer_ctx
    
    try:
        # Ensure table exists
        await checkpointer_instance.setup()
        logger.info("Checkpointer setup complete")
        
        # Compile Graph WITH Checkpointer and store in app.state
        workflow = build_graph()
        app.state.graph = workflow.compile(checkpointer=checkpointer_instance)
        app.state.checkpointer = checkpointer_instance
        app.state.checkpointer_manager = checkpointer
        
        logger.info("Application startup complete")
        
        yield 
        
    finally:
        logger.info("Shutting down: Closing Database connection...")
        await checkpointer.__aexit__(None, None, None)
    
app = FastAPI(title="LangGraph Chatbot API" , lifespan=lifespan)


# --- Endpoints ---

@app.post("/chat", response_model=ChatResponse)
async def chat(request:ChatRequest):
    """
    Standard REST endpoint.
    LangGraph automatically retrieves history, sends to OpenRouter, and save state.    
    """
    graph = app.state.graph
    config = {"configurable": {"thread_id":request.session_id}}
    
    input_messages = HumanMessage(content=request.message)
    
    # Invoke the Graph
    final_state = await graph.ainvoke(
        {"messages":[input_messages]},
        config = config
    )
    
    ai_message = final_state["messages"][-1]
    
    return ChatResponse(
        response= ai_message.content,
        session_id= request.session_id
    ) 
    
@app.websocket("/ws/chat/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    """
    Websocket endpoint that streams OpenRouter tokens in real-time.
    """
    await websocket.accept()
    graph = app.state.graph
    config = {"configurable": {"thread_id" :session_id}}
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_text = message_data.get("message")
            
            if not user_text:
                continue
            
            # Stream events from the graph
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=user_text)]},
                config = config,
                version = "v2"
            ):
                kind = event["event"]
                # Stream actual tokens from the OpenRouter model
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        await websocket.send_json({
                            "type" : "token",
                            "content" : content
                        })
                        
            await websocket.send_json({"type":"complete"})
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Websocket error: {e}")
        await websocket.close()
        
@app.get("/conversation/{session_id}/history", response_model=HistoryResponse)
async def get_history(session_id:str):
    """
    Retrieve history directly from LangGraph's Postgres state.
    """
    graph = app.state.graph
    config = {"configurable": {"thread_id":session_id}}
    
    state_snapshot = await graph.aget_state(config)
    
    formatted_messages = []
    if state_snapshot.values:
        messages = state_snapshot.values.get("messages", [])
        for msg in messages:
            role = "user"
            if isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, SystemMessage):
                role = "system"
                
            formatted_messages.append(MessageDto(
                role = role,
                content = msg.content,
                timestamp=str(datetime.now())
            ))
    return HistoryResponse(
        session_id=session_id,
        messages=formatted_messages
    )