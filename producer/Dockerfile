FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY telemetry_producer.py .
COPY vsat_producer.py .

CMD ["python", "telemetry_producer.py"]

