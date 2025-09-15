FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/services/dialog-engine

ENV PYTHONPATH=/app

EXPOSE 8100

CMD ["python", "-m", "services.dialog-engine.app"]

