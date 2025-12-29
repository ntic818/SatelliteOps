import json
import os
import pika
import requests
import yaml
from influxdb import InfluxDBClient
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from threading import Thread
from queue import Queue

with open('/app/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

llm_queues = list(config['llm_queues'].values())
batch_size = int(os.getenv('ANALYZER_BATCH_SIZE', config['analyzer']['batch_size']))
workers = int(os.getenv('ANALYZER_WORKERS', 4))
prefetch = int(os.getenv('ANALYZER_PREFETCH', 10))

rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://user:password@rabbitmq:5672/')
xai_api_key = os.getenv('XAI_API_KEY')
influxdb_host = 'influxdb'
influxdb_port = 8086
influxdb_username = os.getenv('INFLUXDB_USERNAME', 'telegraf')
influxdb_password = os.getenv('INFLUXDB_PASSWORD', 'telegrafpassword')
influxdb_db = os.getenv('INFLUXDB_DB', 'telemetry')

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_influx_client():
    return InfluxDBClient(host=influxdb_host, port=influxdb_port, username=influxdb_username, password=influxdb_password, database=influxdb_db)

client = get_influx_client()

def worker(queue_name):
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_connection():
        params = pika.URLParameters(rabbitmq_url)
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.queue_declare(queue=queue_name, durable=True)
        ch.basic_qos(prefetch_count=prefetch)
        return conn, ch

    connection, channel = get_connection()
    batch = []
    msg_queue = Queue()

    def callback(ch, method, properties, body):
        msg_queue.put(json.loads(body))
        ch.basic_ack(delivery_tag=method.delivery_tag)

    channel.basic_consume(queue=queue_name, on_message_callback=callback)

    print(f"Starting worker for {queue_name}...")

    while True:
        try:
            while len(batch) < batch_size:
                data = msg_queue.get(timeout=1)
                batch.append(data)
            analyze_batch(batch, queue_name)
            batch.clear()
        except Exception as e:
            print(f"Error in worker {queue_name}: {e}")
            connection.close()
            raise

def analyze_batch(batch, queue_name):
    prompt = f"Analyze this {queue_name.split('_')[1]} satellite telemetry data for anomalies, insights, and severity score (1-10): {json.dumps(batch)}"
    headers = {
        'Authorization': f'Bearer {xai_api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'grok-beta',  # Update if needed for 2025
        'messages': [
            {'role': 'system', 'content': 'You are an AI analyst for satellite data. Detect anomalies, provide summaries, and assign a severity score (1-10).'},
            {'role': 'user', 'content': prompt}
        ]
    }
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def send_request():
        response = requests.post('https://api.x.ai/v1/chat/completions', headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    try:
        insights = send_request()
        write_insights(insights, queue_name)
    except Exception as e:
        print(f"LLM error for {queue_name}: {e}")

def write_insights(insights, queue_name):
    points = [
        {
            "measurement": "insights",
            "tags": {"source": "llm", "category": queue_name.split('_')[1]},
            "time": datetime.utcnow().isoformat(),
            "fields": {"text": insights}
        }
    ]
    client.write_points(points)
    print(f"Wrote insights for {queue_name}: {insights}")

# Start workers
threads = []
for q in llm_queues:
    t = Thread(target=worker, args=(q,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()
