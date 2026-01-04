#!/usr/bin/env python3
import sys
import datetime
import requests

# ======================
# RabbitMQ Test
# ======================
try:
    import pika

    rabbitmq_host = 'localhost'          # Update if different
    rabbitmq_queue = 'telemetry_vsat_queue'
    rabbitmq_user = 'user'               # <-- replace with your working username
    rabbitmq_pass = 'password'           # <-- replace with your working password

    credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_pass)
    parameters = pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Declare the queue (durable)
    channel.queue_declare(queue=rabbitmq_queue, durable=True)

    # Send test message
    test_message = 'Test VSAT message'
    channel.basic_publish(
        exchange='',
        routing_key=rabbitmq_queue,
        body=test_message,
        properties=pika.BasicProperties(
            delivery_mode=2,  # make message persistent
        )
    )
    connection.close()
    print(f"🔹 Testing RabbitMQ...\n✅ Sent test message to RabbitMQ queue '{rabbitmq_queue}': {test_message}\n")
except Exception as e:
    print(f"🔹 Testing RabbitMQ...\n❌ Could not connect to RabbitMQ: {e}\n")


# ======================
# InfluxDB Test
# ======================
try:
    from influxdb import InfluxDBClient

    influx_host = 'localhost'
    influx_port = 8086
    influx_db = 'telemetry_db'

    client = InfluxDBClient(host=influx_host, port=influx_port)

    # Create DB if it does not exist
    databases = client.get_list_database()
    if not any(db['name'] == influx_db for db in databases):
        client.create_database(influx_db)
        print(f"🔹 Testing InfluxDB...\n✅ Database '{influx_db}' created.")
    else:
        print(f"🔹 Testing InfluxDB...\n✅ Database '{influx_db}' already exists.")

    client.switch_database(influx_db)

    # Insert test data
    now = datetime.datetime.now(datetime.timezone.utc)
    test_point = [
        {
            "measurement": "vsat",
            "tags": {"vsat_id": "vsat_test"},
            "time": now.isoformat(),
            "fields": {"signal_strength": 78.0, "tx_power": 123.0, "rx_power": 456.0}
        }
    ]
    client.write_points(test_point)
    print("✅ Test data written to 'telemetry_db'")

    # Read latest data
    result = client.query('SELECT * FROM vsat ORDER BY time DESC LIMIT 3')
    points = list(result.get_points())
    print("📊 Latest data from InfluxDB:")
    for p in points:
        print(p)
    print()
except Exception as e:
    print(f"🔹 Testing InfluxDB...\n❌ Could not connect to InfluxDB: {e}\n")


# ======================
# Kafka Test
# ======================
try:
    from kafka import KafkaProducer

    kafka_host = 'localhost:9092'  # If inside Docker, may need 'kafka:9092'
    kafka_topic = 'telemetry_vsat_queue'

    producer = KafkaProducer(bootstrap_servers=kafka_host)
    producer.send(kafka_topic, b'Test VSAT message')
    producer.flush()
    print(f"🔹 Testing Kafka...\n✅ Sent test message to Kafka queue '{kafka_topic}': Test VSAT message\n")
except Exception as e:
    print(f"🔹 Testing Kafka...\n❌ Could not connect to Kafka: {e}\n")


# ======================
# Prometheus / Grafana Test
# ======================
try:
    prometheus_endpoints = [
        'http://localhost:9090/metrics',   # Prometheus
        'http://localhost:9100/metrics',   # Node Exporter
        'http://localhost:9419/metrics',   # RabbitMQ Exporter
    ]

    print("🔹 Testing Prometheus/Grafana endpoints...")
    for url in prometheus_endpoints:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                print(f"✅ {url} is UP")
            else:
                print(f"❌ {url} returned status {r.status_code}")
        except Exception as e:
            print(f"❌ Could not reach {url}: {e}")
    print()
except Exception as e:
    print(f"🔹 Testing Prometheus/Grafana...\n❌ Error: {e}\n")


print("🎯 All tests completed.")
