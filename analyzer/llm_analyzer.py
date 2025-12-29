import json
import os
import pika
import requests
import yaml
from influxdb import InfluxDBClient
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from threading import Thread
import logging
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
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

# Validate XAI API Key
if not xai_api_key or xai_api_key == 'your_xai_api_key':
    logger.warning("XAI_API_KEY not set or is placeholder! LLM analysis will fail.")

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_influx_client():
    """Create InfluxDB client with retry logic"""
    logger.info(f"Connecting to InfluxDB at {influxdb_host}:{influxdb_port}")
    return InfluxDBClient(
        host=influxdb_host,
        port=influxdb_port,
        username=influxdb_username,
        password=influxdb_password,
        database=influxdb_db,
        timeout=10
    )

influx_client = get_influx_client()

def worker(queue_name):
    """Worker thread to consume and analyze messages from a specific queue"""
    
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    def get_connection():
        logger.info(f"[{queue_name}] Connecting to RabbitMQ...")
        params = pika.URLParameters(rabbitmq_url)
        params.heartbeat = 600
        params.blocked_connection_timeout = 300
        
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.queue_declare(queue=queue_name, durable=True)
        ch.basic_qos(prefetch_count=prefetch)
        return conn, ch

    connection, channel = get_connection()
    batch = []
    last_batch_time = time.time()
    batch_timeout = 30  # Process batch after 30 seconds even if not full

    def callback(ch, method, properties, body):
        """Callback for each message received"""
        nonlocal last_batch_time
        
        try:
            data = json.loads(body)
            batch.append(data)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
            # Process batch when full or timeout reached
            current_time = time.time()
            if len(batch) >= batch_size or (batch and current_time - last_batch_time > batch_timeout):
                try:
                    analyze_batch(batch[:], queue_name)
                    batch.clear()
                    last_batch_time = current_time
                    logger.info(f"[{queue_name}] Processed batch, queue has ~{ch.get_waiting_message_count()} messages remaining")
                except Exception as e:
                    logger.error(f"[{queue_name}] Error analyzing batch: {e}", exc_info=True)
                    # Keep batch and try again later
                    
        except json.JSONDecodeError as e:
            logger.error(f"[{queue_name}] Invalid JSON message: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)  # Acknowledge bad message
        except Exception as e:
            logger.error(f"[{queue_name}] Error in callback: {e}", exc_info=True)

    # Register consumer
    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    logger.info(f"[{queue_name}] Worker started, waiting for messages...")
    
    try:
        # Start consuming - THIS WAS THE MISSING LINE!
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info(f"[{queue_name}] Shutting down worker...")
        channel.stop_consuming()
    except pika.exceptions.AMQPError as e:
        logger.error(f"[{queue_name}] RabbitMQ error: {e}")
        raise
    except Exception as e:
        logger.error(f"[{queue_name}] Unexpected error: {e}", exc_info=True)
        raise
    finally:
        try:
            connection.close()
        except:
            pass

def analyze_batch(batch, queue_name):
    """Send batch to LLM for analysis and store insights"""
    category = queue_name.split('_')[1]  # Extract category from queue name
    
    # Create analysis prompt
    prompt = f"""Analyze this {category} satellite telemetry data batch ({len(batch)} records).

Data: {json.dumps(batch, indent=2)}

Please provide:
1. Summary of key metrics and trends
2. Any anomalies or unusual patterns detected
3. Severity score (1-10, where 10 is critical)
4. Recommended actions if any issues found

Format your response as JSON with keys: summary, anomalies, severity, recommendations"""

    headers = {
        'Authorization': f'Bearer {xai_api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': 'grok-beta',
        'messages': [
            {
                'role': 'system',
                'content': 'You are an expert AI analyst for satellite telemetry data. Detect anomalies, provide insights, and assign severity scores. Always respond in valid JSON format.'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': 0.3,  # Lower temperature for more consistent analysis
        'max_tokens': 1000
    }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def send_request():
        response = requests.post(
            'https://api.x.ai/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    try:
        logger.info(f"[{queue_name}] Sending batch of {len(batch)} records to LLM...")
        insights = send_request()
        
        # Try to parse as JSON, fall back to text if needed
        try:
            insights_json = json.loads(insights)
            severity = insights_json.get('severity', 5)
        except json.JSONDecodeError:
            logger.warning(f"[{queue_name}] LLM response not valid JSON, storing as text")
            severity = 5  # Default severity
        
        write_insights(insights, category, severity, queue_name)
        logger.info(f"[{queue_name}] ✓ Analysis complete (severity: {severity})")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"[{queue_name}] LLM API error: {e}")
        # Write error insight to InfluxDB
        error_insight = f"LLM analysis failed: {str(e)}"
        write_insights(error_insight, category, 0, queue_name)
    except Exception as e:
        logger.error(f"[{queue_name}] Unexpected error during analysis: {e}", exc_info=True)

def write_insights(insights, category, severity, queue_name):
    """Write insights to InfluxDB"""
    points = [
        {
            "measurement": "insights",
            "tags": {
                "source": "llm",
                "category": category,
                "queue": queue_name
            },
            "time": datetime.utcnow().isoformat(),
            "fields": {
                "text": str(insights)[:10000],  # Limit text size
                "severity": float(severity)
            }
        }
    ]
    
    try:
        influx_client.write_points(points)
        logger.debug(f"[{queue_name}] Wrote insights to InfluxDB")
    except Exception as e:
        logger.error(f"[{queue_name}] Error writing to InfluxDB: {e}", exc_info=True)

def main():
    """Start worker threads for all LLM queues"""
    logger.info("=" * 60)
    logger.info("LLM Analyzer Starting")
    logger.info(f"Workers: {workers}")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Prefetch: {prefetch}")
    logger.info(f"Queues: {', '.join(llm_queues)}")
    logger.info("=" * 60)
    
    threads = []
    
    # Start worker thread for each queue
    for queue in llm_queues:
        t = Thread(target=worker, args=(queue,), name=f"Worker-{queue}", daemon=False)
        t.start()
        threads.append(t)
        logger.info(f"Started worker thread for {queue}")
    
    logger.info(f"All {len(threads)} worker threads started")
    
    # Wait for all threads
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, waiting for workers to finish...")
        for t in threads:
            t.join(timeout=5)
    
    logger.info("Analyzer shut down cleanly")

if __name__ == "__main__":
    main()
