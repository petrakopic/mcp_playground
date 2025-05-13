# ---------- builder stage purely to grab the uv binary ----------
    FROM ghcr.io/astral-sh/uv:0.7.3 AS uvfetch

    # ---------- final stage ----------
    FROM python:3.12-slim
    
    # 1️⃣  system bits you may need (Snowflake libs sometimes want gcc / libssl)
    RUN apt-get update && \
        apt-get install -y --no-install-recommends build-essential curl && \
        rm -rf /var/lib/apt/lists/*
    
    # 2️⃣  drop the uv binary into /usr/local/bin
    COPY --from=uvfetch /uv  /usr/local/bin/uv
    COPY --from=uvfetch /uvx /usr/local/bin/uvx   
    
    # 3️⃣  install Python deps **with uv itself**
    WORKDIR /app
    COPY pyproject.toml requirements.txt ./
    COPY . .
    RUN uv pip install --system -r requirements.txt                   
    
    # 4️⃣  Streamlit settings for Heroku
    ENV STREAMLIT_SERVER_HEADLESS=true \
        STREAMLIT_SERVER_ADDRESS=0.0.0.0
    
    EXPOSE 8501
    
    CMD ["bash","-c","streamlit run app.py --server.port=$PORT --server.address=0.0.0.0"]