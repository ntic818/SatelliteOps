import time
import json
import yaml
import os
from kafka import KafkaProducer
from pysnmp.hlapi import *

CONFIG_PATH = "/app/config.yaml"
KAFKA_TOPIC = "telemetry.vsat"
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
POLL_INTERVAL = 15  # seconds


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def snmp_get(ip, community, oid):
    """
    Returns SNMP value or None
    """
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),
            UdpTransportTarget((ip, 161), timeout=2, retries=1),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
        )

        error_indication, error_status, error_index, var_binds = next(iterator)

        if error_indication or error_status:
            return None

        for _, value in var_binds:
            return float(value)

    except Exception:
        return None


def main():
    print("🚀 Starting MULTI-VSAT SNMP producer")

    config = load_config()
    vsats = config.get("vsats", {})

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    while True:
        for vsat_id, vsat in vsats.items():
            ip = vsat["ip"]
            community = vsat.get("community", "public")
            oids = vsat.get("oids", {})

            payload = {
                "timestamp": time.time(),
                "category": "vsat",
                "vsat_id": vsat_id,
                "vsat_ip": ip,
            }

            for metric, oid in oids.items():
                payload[metric] = snmp_get(ip, community, oid)

            producer.send(KAFKA_TOPIC, payload)
            print(f"📡 Sent {vsat_id}: {payload}")

        producer.flush()
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

