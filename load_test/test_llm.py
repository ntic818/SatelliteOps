import time
from influxdb import InfluxDBClient
import os
import uuid

INFLUX_HOST = os.getenv("INFLUX_HOST", "localhost")
INFLUX_DB = "telemetry_db"

TEST_ID = f"TEST-{uuid.uuid4()}"


def write_test_point():
    client = InfluxDBClient(
        host=INFLUX_HOST,
        port=8086,
        database=INFLUX_DB
    )

    json_body = [
        {
            "measurement": "vsat_test",  # 👈 isolated test measurement
            "tags": {
                "test_id": TEST_ID,
                "vsat_id": "TEST_VSAT"
            },
            "fields": {
                "rx_power": 111.0,
                "tx_power": 222.0,
                "signal_strength": 33.0
            }
        }
    ]

    client.write_points(json_body)
    print("✅ Test telemetry written to InfluxDB")


def test_llm_analysis():
    client = InfluxDBClient(
        host=INFLUX_HOST,
        port=8086,
        database=INFLUX_DB
    )

    result = client.query(
        f"SELECT * FROM vsat_test WHERE test_id='{TEST_ID}' ORDER BY time DESC LIMIT 1"
    )

    points = list(result.get_points())
    assert points, "❌ No telemetry found for LLM analysis"

    p = points[0]
    print("🔍 LLM analyzing telemetry:", p)

    # Mock LLM logic
    if p["signal_strength"] < 40:
        summary = "⚠️ Weak signal detected"
    else:
        summary = "✅ Signal healthy"

    print("🧠 LLM Result:", summary)


if __name__ == "__main__":
    write_test_point()
    time.sleep(2)
    test_llm_analysis()
