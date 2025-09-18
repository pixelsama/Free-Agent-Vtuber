FROM python:3.11-slim

WORKDIR /app/services/async-workers

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/services/async-workers

ENV PYTHONPATH=/app

CMD ["python", "ltm_worker.py"]
