import json
import os
import time
import random
import yaml
from kafka import KafkaProducer
from tenacity import retry, stop_after_attempt, wait_exponential

with open('/app/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

topics = config['topics']

bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_producer():
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

producer = get_producer()

print("Starting telemetry producer...")

categories = list(topics.keys())

while True:
    category = random.choice(categories)
    data = {
        'timestamp': time.time(),
        'category': category,
        'temperature': random.uniform(20.0, 30.0) if category in ['health', 'environment'] else None,
        'altitude': random.uniform(500.0, 1000.0) if category == 'attitude' else None,
        'pressure': random.uniform(900.0, 1100.0) if category == 'environment' else None,
        'power_level': random.uniform(80.0, 100.0) if category == 'power' else None,
        'status': random.choice(['nominal', 'warning', 'error'])
    }
    data = {k: v for k, v in data.items() if v is not None}  # Clean None values
    topic = topics[category]
    try:
        producer.send(topic, data)
        print(f"Sent to {topic}: {data}")
    except Exception as e:
        print(f"Error sending: {e}")
        raise  # For retry
    time.sleep(1)
