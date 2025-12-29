import json
import os
import pika
import yaml
from kafka import KafkaConsumer
from tenacity import retry, stop_after_attempt, wait_exponential

with open('/app/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

topics = list(config['topics'].values())
queues = config['queues']

bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://user:password@rabbitmq:5672/')

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_consumer():
    return KafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest'
    )

consumer = get_consumer()

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_rabbit_connection():
    params = pika.URLParameters(rabbitmq_url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    for q in queues.values():
        channel.queue_declare(queue=q, durable=True)
    return connection, channel

connection, channel = get_rabbit_connection()

print("Starting router...")

for message in consumer:
    data = message.value
    category = data.get('category', 'raw')
    queue = queues.get(category, queues['raw'])
    try:
        channel.basic_publish(exchange='', routing_key=queue, body=json.dumps(data))
        print(f"Routed to {queue}: {data}")
    except Exception as e:
        print(f"Error routing: {e}")
        connection.close()
        raise  # Retry connection

connection.close()
