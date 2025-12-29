#!/bin/bash

# List of containers you want to capture logs from
containers=("grafana" "telegraf" "producer" "router" "analyzer" "kafka" "rabbitmq" "influxdb")

# Log file where logs will be saved
log_file="/home/gilat/Desktop/project/SateliteOps/logs/combined_logs.log"

# Loop through the containers and capture logs
for container in "${containers[@]}"; do
  echo "Capturing logs for $container..."
  # Start tailing logs for each container in the background and save it to the log file
  docker logs -f "$container" >> "$log_file" &
done

# Wait for all background processes (log tails) to finish
wait
