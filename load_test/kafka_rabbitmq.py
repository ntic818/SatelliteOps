#!/usr/bin/env python3
import pika

# =========================
# RABBITMQ CONFIGURATION
# =========================
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'testuser'         # replace with your RabbitMQ username
RABBITMQ_PASSWORD = 'testpassword' # replace with your RabbitMQ password
QUEUE_NAME = 'telemetry_vsat_queue'

# =========================
# CONNECT TO RABBITMQ
# =========================
credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
parameters = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=RABBITMQ_PORT,
    virtual_host='/',
    credentials=credentials
)

try:
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # Match the existing queue's durability (durable=True)
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    # Publish a test message
    test_message = "Test VSAT message"
    channel.basic_publish(
        exchange='',
        routing_key=QUEUE_NAME,
        body=test_message,
        properties=pika.BasicProperties(
            delivery_mode=2  # make message persistent
        )
    )

    print(f"✅ Sent test message to RabbitMQ queue '{QUEUE_NAME}': {test_message}")
    connection.close()

except pika.exceptions.AMQPConnectionError as e:
    print(f"❌ Could not connect to RabbitMQ: {e}")
except Exception as e:
    print(f"❌ Error: {e}")

