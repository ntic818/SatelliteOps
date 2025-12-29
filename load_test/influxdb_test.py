#!/usr/bin/env python3
from influxdb import InfluxDBClient
import datetime

# =========================
# INFLUXDB CONFIGURATION
# =========================
INFLUXDB_HOST = 'localhost'
INFLUXDB_PORT = 8086
INFLUXDB_USER = 'root'
INFLUXDB_PASSWORD = 'root'
DB_NAME = 'telemetry_db'

try:
    # Connect to InfluxDB
    client = InfluxDBClient(
        host=INFLUXDB_HOST,
        port=INFLUXDB_PORT,
        username=INFLUXDB_USER,
        password=INFLUXDB_PASSWORD
    )

    # Create DB if it doesn't exist
    databases = [db['name'] for db in client.get_list_database()]
    if DB_NAME not in databases:
        client.create_database(DB_NAME)
        print(f"✅ Database '{DB_NAME}' created.")
    else:
        print(f"✅ Database '{DB_NAME}' already exists.")

    client.switch_database(DB_NAME)

    # Write test VSAT data
    test_data = [
        {
            "measurement": "vsat",
            "tags": {
                "vsat_id": "vsat_test"
            },
            "time": datetime.datetime.utcnow().isoformat() + 'Z',
            "fields": {
                "signal_strength": 78.0,
                "tx_power": 123.0,
                "rx_power": 456.0
            }
        }
    ]
    client.write_points(test_data)
    print(f"✅ Test data written to '{DB_NAME}'")

    # Query back the data
    result = client.query('SELECT * FROM vsat LIMIT 5')
    points = list(result.get_points(measurement='vsat'))
    if points:
        print("📊 Latest data from InfluxDB:")
        for point in points:
            print(point)
    else:
        print("⚠️ No data found in InfluxDB.")

except Exception as e:
    print(f"❌ Error connecting to InfluxDB: {e}")

