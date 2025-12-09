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
class State(TypedDict):
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
    
    # 3. Define Node 
    async def generate_response(state: State):
        response = await chain.ainvoke(state["messages"])
        return {"messages":[AIMessage(content=response.content)]}
    
    # 4. Define Edges (Simple Linear Flow)
    graph = StateGraph(State)
    graph.add_node("chatbot", generate_response)
    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", END)
    
    return graph
    
# --- FastAPI Lifespan (connection Management) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: Connecting to Database...")
    
    try:
        async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
            await checkpointer.setup()
            logger.info("Checkpointer setup complete")
            
            workflow = build_graph()
            app.state.graph = workflow.compile(checkpointer=checkpointer)
            
            logger.info("Application startup complete")
            yield
            
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        raise
    finally:
        logger.info("Shutting down")
    
app = FastAPI(title="LangGraph Chatbot API" , lifespan=lifespan)


# --- Endpoints ---
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
        
        
@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}