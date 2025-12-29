import json
import os
import pika
import yaml
from kafka import KafkaConsumer
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
with open('/app/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

topics = list(config['topics'].values())
queues = config['queues']
llm_queues = config['llm_queues']

bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://user:password@rabbitmq:5672/')

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_consumer():
    """Create Kafka consumer with retry logic"""
    logger.info(f"Connecting to Kafka at {bootstrap_servers}")
    return KafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='router-group'
    )

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
def get_rabbit_connection():
    """Create RabbitMQ connection and declare queues"""
    logger.info(f"Connecting to RabbitMQ at {rabbitmq_url}")
    params = pika.URLParameters(rabbitmq_url)
    params.heartbeat = 600
    params.blocked_connection_timeout = 300
    
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    
    # Declare all telemetry queues (for Telegraf)
    for queue_name, queue_value in queues.items():
        channel.queue_declare(queue=queue_value, durable=True)
        logger.info(f"Declared telemetry queue: {queue_value}")
    
    # Declare all LLM queues (for Analyzer)
    for queue_name, queue_value in llm_queues.items():
        channel.queue_declare(queue=queue_value, durable=True)
        logger.info(f"Declared LLM queue: {queue_value}")
    
    return connection, channel

def main():
    """Main routing loop"""
    consumer = get_consumer()
    connection, channel = get_rabbit_connection()
    
    logger.info("=" * 60)
    logger.info("Router started successfully!")
    logger.info(f"Subscribed to Kafka topics: {', '.join(topics)}")
    logger.info(f"Routing to {len(queues)} telemetry queues and {len(llm_queues)} LLM queues")
    logger.info("=" * 60)
    
    message_count = 0
    
    try:
        for message in consumer:
            data = message.value
            category = data.get('category', 'raw')
            
            # Get queue names for this category
            telemetry_queue = queues.get(category, queues['raw'])
            llm_queue = llm_queues.get(category, llm_queues['raw'])
            
            try:
                # Publish to telemetry queue (for Telegraf → InfluxDB)
                channel.basic_publish(
                    exchange='',
                    routing_key=telemetry_queue,
                    body=json.dumps(data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Persistent message
                        content_type='application/json'
                    )
                )
                
                # Publish to LLM queue (for Analyzer)
                channel.basic_publish(
                    exchange='',
                    routing_key=llm_queue,
                    body=json.dumps(data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json'
                    )
                )
                
                message_count += 1
                if message_count % 100 == 0:
                    logger.info(f"Routed {message_count} messages (last: {category})")
                else:
                    logger.debug(f"Routed to {telemetry_queue} and {llm_queue}: {data}")
                    
            except pika.exceptions.AMQPError as e:
                logger.error(f"RabbitMQ error while routing: {e}")
                # Reconnect
                connection.close()
                connection, channel = get_rabbit_connection()
                logger.info("Reconnected to RabbitMQ")
                
            except Exception as e:
                logger.error(f"Unexpected error routing message: {e}", exc_info=True)
                
    except KeyboardInterrupt:
        logger.info("Shutting down router...")
    except Exception as e:
        logger.error(f"Fatal error in router: {e}", exc_info=True)
        raise
    finally:
        consumer.close()
        connection.close()
        logger.info("Router shut down cleanly")

if __name__ == "__main__":
    main()
