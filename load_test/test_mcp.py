#!/usr/bin/env python3
import json
import time
import uuid
from kafka import KafkaProducer, KafkaConsumer
import pika

# --- CONFIG ---
KAFKA_BROKER = "kafka:9092"  # Use Docker container name on same network
KAFKA_TOPIC = "telemetry_vsat"
RABBITMQ_URL = "amqp://user:password@rabbitmq:5672/"
RABBITMQ_QUEUE = "telemetry_vsat_queue"
MAX_ATTEMPTS = 10
SLEEP_BETWEEN_ATTEMPTS = 2

# --- KAFKA PRODUCER ---
def send_kafka_message(msg):
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    producer.send(KAFKA_TOPIC, value=msg)
    producer.flush()
    print(f"✅ Sent test message to Kafka: {msg}")
    producer.close()

# --- RABBITMQ CONSUMER ---
def get_message_from_rabbitmq(test_id):
    credentials = pika.PlainCredentials('user', 'password')
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='rabbitmq', credentials=credentials)
    )
    channel = connection.channel()
    method_frame, header_frame, body = None, None, None

    for _ in range(MAX_ATTEMPTS):
        method_frame, header_frame, body = channel.basic_get(queue=RABBITMQ_QUEUE, auto_ack=True)
        if body:
            message = json.loads(body)
            if message.get("test_id") == test_id:
                connection.close()
                return message
        time.sleep(SLEEP_BETWEEN_ATTEMPTS)

    connection.close()
    return None

# --- TEST FUNCTION ---
def test_mcp():
    test_id = f"TEST-{uuid.uuid4()}"
    kafka_msg = {
        "test_id": test_id,
        "category": "vsat",
        "vsat_id": "TEST_VSAT",
        "rx_power": 999.0,
        "tx_power": 888.0,
        "signal_strength": 77.7,
        "timestamp": time.time()
    }

    print("🔹 Testing MCP (Kafka → RabbitMQ)...")
    send_kafka_message(kafka_msg)

    print("⏳ Waiting for router Kafka → RabbitMQ...")
    received = get_message_from_rabbitmq(test_id)

    if received:
        print(f"✅ RabbitMQ message received: {received}")
    else:
        raise RuntimeError(f"❌ No matching message received from RabbitMQ after {MAX_ATTEMPTS} attempts")

if __name__ == "__main__":
    test_mcp()
