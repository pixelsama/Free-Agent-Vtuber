FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src /app/src
COPY tests /app/tests

ENV PYTHONPATH=/app/src

ENV ENABLE_REAL_LLM=false \
    LLM_MODEL=gpt-4o-mini \
    LLM_TEMPERATURE=0.7 \
    LLM_MAX_TOKENS=1024 \
    LLM_TOP_P=1.0 \
    LLM_FREQUENCY_PENALTY=0.0 \
    LLM_PRESENCE_PENALTY=0.0 \
    LLM_REQUEST_TIMEOUT=30 \
    LLM_RETRY_LIMIT=2 \
    LLM_RETRY_BACKOFF_SECONDS=0.5 \
    ENABLE_SHORT_TERM_MEMORY=true \
    STM_DB_PATH=/app/data/dialog_memory.sqlite \
    STM_CONTEXT_TURNS=20 \
    LTM_BASE_URL=http://memory-python:8200 \
    LTM_RETRIEVE_PATH=/v1/memory/retrieve \
    LTM_RETRIEVE_TIMEOUT=3 \
    LTM_MAX_SNIPPETS=5

EXPOSE 8100

CMD ["python", "-m", "dialog_engine.app"]
