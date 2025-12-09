# Use lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for asyncpg build sometimes)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY chatbot_langgraph.py .

# DON'T copy .env file - use Docker environment variables instead
# If you have a .env, add it to .dockerignore

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "chatbot_langgraph:app", "--host", "0.0.0.0", "--port", "8000"]