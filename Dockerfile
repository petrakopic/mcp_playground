# Use official slim Python base
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y curl git build-essential

# Install uv package manager from Astral
RUN curl -Ls https://astral.sh/uv/install.sh | bash

# Add uv to path
ENV PATH="/root/.cargo/bin:$PATH"

# Set the working directory inside the container
WORKDIR /app

# Copy your project files
COPY . /app

# Install Python dependencies
RUN uv pip install -r requirements.txt

# Expose Streamlit port (default)
EXPOSE 8501

# Start your Streamlit app (this is your current entrypoint)
CMD ["streamlit", "run", "src/mcp_snowflake_server/app.py"]

