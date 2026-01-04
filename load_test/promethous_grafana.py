import requests

endpoints = [
    'http://localhost:9090/metrics',        # Prometheus
    'http://localhost:9100/metrics',        # Node Exporter
    'http://localhost:9419/metrics'         # RabbitMQ Exporter
]

for url in endpoints:
    r = requests.get(url)
    if r.status_code == 200:
        print(f"{url} is UP")
    else:
        print(f"{url} is DOWN with status {r.status_code}")
