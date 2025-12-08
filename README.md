# LangGraph Chatbot

A modern, full-stack chatbot application built with LangGraph, FastAPI, and Streamlit. This chatbot uses OpenRouter API for AI model inference and PostgreSQL for conversation state management.

## Features

- 🤖 **AI-Powered Chat**: Powered by OpenRouter API with support for various LLM models
- 🔄 **Conversation State Management**: Persistent conversation history using PostgreSQL
- 🌐 **Real-time Streaming**: WebSocket support for streaming responses
- 🐳 **Dockerized**: Fully containerized with Docker Compose for easy deployment
- 🎨 **Modern UI**: Clean Streamlit-based frontend
- 📡 **REST & WebSocket APIs**: Flexible API options for different use cases

## Architecture

```
┌─────────────┐
│  Streamlit  │  Frontend (Port 8501)
│   Frontend  │
└──────┬──────┘
       │
       │ HTTP/WebSocket
       │
┌──────▼──────┐
│   FastAPI   │  Backend (Port 8000)
│   Backend   │
└──────┬──────┘
       │
       ├───────────┐
       │           │
┌──────▼──────┐  ┌─▼────────────┐
│ PostgreSQL  │  │  OpenRouter  │
│  Database   │  │     API      │
│  (Port 5432)│  └──────────────┘
└─────────────┘
```

## Prerequisites

- Docker and Docker Compose installed
- OpenRouter API key ([Get one here](https://openrouter.ai/))
- Git (for cloning the repository)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd Chatbot
   ```

2. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```bash
   cp .env.example .env
   ```
   
   Then edit `.env` and add your OpenRouter API key:
   ```env
   OPENROUTER_API_KEY=your_api_key_here
   ```

3. **Start the application**
   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:8501
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

## Configuration

### Environment Variables

The following environment variables can be configured in `.env`:

- `OPENROUTER_API_KEY`: Your OpenRouter API key (required)
- `MODEL_NAME`: The model to use (default: `tngtech/deepseek-r1t2-chimera:free`)
- `DATABASE_URL`: PostgreSQL connection string (automatically set by docker-compose)

### Model Configuration

You can change the AI model by modifying the `MODEL_NAME` in `docker-compose.yml` or by setting it in your `.env` file. Check [OpenRouter Models](https://openrouter.ai/models) for available models.

## Project Structure

```
Chatbot/
├── backend/
│   ├── chatbot_langgraph.py    # FastAPI backend with LangGraph
│   ├── requirements.txt         # Python dependencies
│   └── Dockerfile              # Backend container config
├── frontend/
│   ├── streamlit_app.py        # Streamlit frontend
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile              # Frontend container config
├── docker-compose.yml          # Docker Compose configuration
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

## API Endpoints

### REST API

- `POST /chat` - Send a chat message
  ```json
  {
    "message": "Hello!",
    "session_id": "your-session-id"
  }
  ```

- `GET /conversation/{session_id}/history` - Get conversation history
  - Returns all messages for a given session

### WebSocket API

- `WS /ws/chat/{session_id}` - Real-time streaming chat
  ```json
  {
    "message": "Your message here"
  }
  ```
  - Streams tokens as they are generated
  - Sends `{"type": "token", "content": "..."}` for each token
  - Sends `{"type": "complete"}` when finished

## Development

### Running Locally (without Docker)

1. **Set up PostgreSQL**
   - Install and run PostgreSQL locally
   - Create a database: `chatbot_db`
   - Update `DATABASE_URL` in your `.env` file

2. **Backend Setup**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn chatbot_langgraph:app --reload
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   pip install -r requirements.txt
   streamlit run streamlit_app.py
   ```

### Modifying the Chatbot

The chatbot's behavior is defined in `backend/chatbot_langgraph.py`:

- **System Prompt**: Modify the system message in the `build_graph()` function
- **Model Parameters**: Adjust temperature and other parameters in the `ChatOpenAI` initialization
- **Graph Logic**: Add nodes and edges to customize the conversation flow

## Technologies Used

- **Backend**:
  - FastAPI - Modern Python web framework
  - LangGraph - Framework for building stateful, multi-actor applications
  - LangChain - LLM application framework
  - PostgreSQL - Relational database
  - asyncpg - Async PostgreSQL driver

- **Frontend**:
  - Streamlit - Rapid web app development framework

- **Infrastructure**:
  - Docker & Docker Compose - Containerization
  - OpenRouter API - LLM inference platform

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL container is healthy: `docker-compose ps`
- Check database logs: `docker-compose logs db`

### API Key Issues
- Verify your OpenRouter API key is correct
- Check that the key has sufficient credits/quota
- Ensure the `.env` file is loaded correctly

### Port Conflicts
- If ports are already in use, modify `docker-compose.yml`:
  - Backend: Change `8000:8000` to `8001:8000`
  - Frontend: Change `8501:8501` to `8502:8501`
  - Database: Change `5432:5432` to `5433:5432`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open source and available under the MIT License.

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) for the graph-based conversation framework
- [OpenRouter](https://openrouter.ai/) for LLM API access
- [FastAPI](https://fastapi.tiangolo.com/) for the excellent web framework
- [Streamlit](https://streamlit.io/) for the frontend framework

