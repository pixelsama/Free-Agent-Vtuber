FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src /app/src
COPY tests /app/tests

ENV PYTHONPATH=/app/src

EXPOSE 8100

CMD ["python", "-m", "dialog_engine.app"]
