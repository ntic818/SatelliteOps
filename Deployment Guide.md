# SatelliteOps - Complete Deployment Guide

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose (for local deployment)

- Kubernetes cluster (for K8s deployment)

- kubectl configured

- xAI API Key (get from https://x.ai)

## 📋 Before You Start

### 1. Replace Fixed Files

Copy these fixed files to your project:

\# Copy fixed router

cp /path/to/fixed/kafka\_to\_rabbitmq.py router/kafka\_to\_rabbitmq.py



\# Copy fixed analyzer

cp /path/to/fixed/llm\_analyzer.py analyzer/llm\_analyzer.py



\# Copy updated docker-compose

cp /path/to/updated/docker-compose.yml docker-compose.yml
### 2. Configure Your xAI API Key

Edit .env file:

XAI\_API\_KEY=your\_actual\_xai\_api\_key\_here
**Get your key from**: https://x.ai/api

## 🐳 Docker Compose Deployment (Recommended for Testing)

### Step 1: Build Docker Images

\# Build all services

docker-compose build



\# Or build individually

docker-compose build producer

docker-compose build router

docker-compose build analyzer
### Step 2: Start All Services

\# Start everything in background

docker-compose up -d



\# Or start with logs visible

docker-compose up
### Step 3: Verify Services

\# Check all containers are running

docker-compose ps



\# Expected output: all services should be "Up"
### Step 4: Monitor Logs

\# View all logs

docker-compose logs -f



\# View specific service

docker-compose logs -f producer

docker-compose logs -f router

docker-compose logs -f analyzer



\# Check for errors

docker-compose logs | grep -i error
### Step 5: Verify Data Flow

#### Check Kafka Topics

docker exec -it kafka kafka-topics \\

&nbsp; --list \\

&nbsp; --bootstrap-server localhost:9092



\# Should see: telemetry.raw, telemetry.power, telemetry.health, etc.
#### Check RabbitMQ Queues

\# Access RabbitMQ Management UI

open http://localhost:15672

\# Login: user / password



\# Or via API

curl -u user:password http://localhost:15672/api/queues
#### Check InfluxDB Data

\# Query telemetry data

curl -G 'http://localhost:8086/query?db=telemetry' \\

&nbsp; --data-urlencode "q=SELECT \* FROM amqp\_consumer LIMIT 10"



\# Query LLM insights

curl -G 'http://localhost:8086/query?db=telemetry' \\

&nbsp; --data-urlencode "q=SELECT \* FROM insights LIMIT 10"
#### Access Grafana Dashboard

\# Open browser

open http://localhost:3000



\# Login

Username: admin

Password: grafanapassword



\# Navigate to "Satellite Telemetry Dashboard"
### Step 6: Test End-to-End Flow

\# 1. Verify producer is sending data

docker logs producer | tail -20



\# 2. Verify router is routing messages

docker logs router | tail -20



\# 3. Verify analyzer is processing batches

docker logs analyzer | tail -20



\# 4. Check InfluxDB has insights

curl -G 'http://localhost:8086/query?db=telemetry' \\

&nbsp; --data-urlencode "q=SELECT count(\*) FROM insights"
## ☸️ Kubernetes Deployment

### Step 1: Build and Push Docker Images

\# Login to your Docker registry

docker login



\# Build images

docker build -t your-docker-repo/satelliteops-producer:latest ./producer

docker build -t your-docker-repo/satelliteops-router:latest ./router

docker build -t your-docker-repo/satelliteops-analyzer:latest ./analyzer



\# Push to registry

docker push your-docker-repo/satelliteops-producer:latest

docker push your-docker-repo/satelliteops-router:latest

docker push your-docker-repo/satelliteops-analyzer:latest
### Step 2: Update Image References

Edit k8s/all-deployments.yaml and replace:

image: your-docker-repo/satelliteops-producer:latest
with your actual registry path.

### Step 3: Configure Secrets

Edit k8s/secrets.yaml and add your actual xAI API key:

XAI\_API\_KEY: "your\_actual\_xai\_api\_key\_here"
**For production**, encode secrets:

echo -n 'your\_xai\_api\_key' | base64
### Step 4: Deploy to Kubernetes

\# Create namespace (optional)

kubectl create namespace satelliteops

kubectl config set-context --current --namespace=satelliteops



\# Apply configurations

kubectl apply -f k8s/configmap.yaml

kubectl apply -f k8s/secrets.yaml

kubectl apply -f k8s/all-deployments.yaml



\# Verify deployment

kubectl get pods

kubectl get services
### Step 5: Check Pod Status

\# Watch pods starting

kubectl get pods -w



\# All pods should reach "Running" status

\# Check for any errors

kubectl get pods | grep -v Running
### Step 6: Check Logs

\# Check producer

kubectl logs -f deployment/producer



\# Check router

kubectl logs -f deployment/router



\# Check analyzer

kubectl logs -f deployment/analyzer



\# Check for errors across all pods

kubectl logs -l app=analyzer | grep -i error
### Step 7: Access Services

\# Port forward Grafana

kubectl port-forward svc/grafana 3000:3000



\# Port forward Prometheus

kubectl port-forward svc/prometheus 9090:9090



\# Port forward RabbitMQ Management

kubectl port-forward svc/rabbitmq 15672:15672



\# Access in browser

open http://localhost:3000  # Grafana

open http://localhost:9090  # Prometheus

open http://localhost:15672 # RabbitMQ
### Step 8: Verify Data Flow

\# Check Kafka topics

kubectl exec -it deployment/kafka -- kafka-topics \\

&nbsp; --list --bootstrap-server localhost:9092



\# Query InfluxDB

kubectl exec -it deployment/influxdb -- \\

&nbsp; influx -database telemetry -execute 'SELECT \* FROM insights LIMIT 10'
## 🧪 Testing & Validation

### Test 1: Producer → Kafka

\# Check producer logs for "Sent to telemetry.\*"

docker logs producer | grep "Sent to"



\# Should see messages like:

\# Sent to telemetry.power: {'timestamp': ..., 'power\_level': ...}
### Test 2: Router → RabbitMQ

\# Check router logs for "Routed to"

docker logs router | grep "Routed to"



\# Should see messages routed to BOTH queues:

\# Routed to telemetry\_power\_queue and llm\_power\_queue
### Test 3: Telegraf → InfluxDB

\# Verify telegraf is consuming from RabbitMQ

docker logs telegraf | grep -i "starting"



\# Query InfluxDB for telemetry data

curl -G 'http://localhost:8086/query?db=telemetry' \\

&nbsp; --data-urlencode "q=SHOW MEASUREMENTS"



\# Should see: amqp\_consumer
### Test 4: Analyzer → InfluxDB

\# Check analyzer logs for "Analysis complete"

docker logs analyzer | grep "Analysis complete"



\# Query for insights

curl -G 'http://localhost:8086/query?db=telemetry' \\

&nbsp; --data-urlencode "q=SELECT \* FROM insights ORDER BY time DESC LIMIT 5"



\# Should see LLM-generated insights
### Test 5: Grafana Visualization

\# Login to Grafana

open http://localhost:3000



\# Go to Dashboard → Satellite Telemetry Dashboard

\# You should see:

\# - Temperature trends (line graph)

\# - LLM insights (text panel)

\# - Anomaly frequency (line graph)

\# - Severity heatmap
## 🐛 Troubleshooting

### Problem: Analyzer not receiving messages

**Symptoms:**

docker logs analyzer

\# Shows: "Starting worker for llm\_power\_queue..."

\# But no "Analysis complete" messages
**Solution:**

1. Check router is sending to LLM queues:

docker logs router | grep "llm\_"
2. Verify LLM queues exist in RabbitMQ:

curl -u user:password http://localhost:15672/api/queues | jq '.\[].name'
3. Check analyzer queue connection:

docker logs analyzer | grep "Connecting to RabbitMQ"
### Problem: LLM API errors

**Symptoms:**

docker logs analyzer | grep "LLM API error"
**Solutions:**

1. Verify API key is set:

docker exec analyzer printenv XAI\_API\_KEY
2. Check API key is valid at https://x.ai

3. Check rate limits on xAI API

### Problem: No data in InfluxDB

**Symptoms:**

curl -G 'http://localhost:8086/query?db=telemetry' \\

&nbsp; --data-urlencode "q=SELECT \* FROM amqp\_consumer LIMIT 1"

\# Returns empty result
**Solutions:**

1. Check Telegraf is running:

docker logs telegraf | grep -i error
2. Verify RabbitMQ queues have messages:

curl -u user:password http://localhost:15672/api/queues
3. Check Telegraf config:

docker exec telegraf cat /etc/telegraf/telegraf.conf
### Problem: Services not starting in Kubernetes

**Symptoms:**

kubectl get pods

\# Shows pods in "CrashLoopBackOff" or "Error"
**Solutions:**

1. Check pod logs:

kubectl logs pod-name

kubectl describe pod pod-name
2. Verify secrets are created:

kubectl get secrets

kubectl describe secret app-secrets
3. Check configmaps:

kubectl get configmaps

kubectl describe configmap app-config
## 📊 Monitoring

### Prometheus Metrics

Access Prometheus: http://localhost:9090

Key queries:


\# Kafka message rate

rate(kafka\_server\_brokertopicmetrics\_messagesin\_total\[5m])



\# RabbitMQ queue depth

rabbitmq\_queue\_messages



\# Container CPU usage

rate(container\_cpu\_usage\_seconds\_total\[5m])



\# Container memory usage

container\_memory\_usage\_bytes

### Grafana Dashboards

Access Grafana: http://localhost:3000

**Pre-configured dashboards:**

1. Satellite Telemetry Dashboard

  - Temperature trends

  - LLM insights

  - Anomaly frequency

  - Severity heatmap

2. System Monitoring (create from Prometheus datasource)

  - CPU usage

  - Memory usage

  - Network I/O

  - Disk usage

## 🔧 Maintenance

### Scaling Services

**Docker Compose:**

\# Scale analyzer to 3 instances

docker-compose up -d --scale analyzer=3
**Kubernetes:**

\# Scale analyzer replicas

kubectl scale deployment analyzer --replicas=3



\# Auto-scale based on CPU

kubectl autoscale deployment analyzer \\

&nbsp; --min=2 --max=10 --cpu-percent=80
### Backup Data

**InfluxDB:**

\# Backup

docker exec influxdb influxd backup -portable /tmp/backup

docker cp influxdb:/tmp/backup ./influxdb-backup



\# Restore

docker cp ./influxdb-backup influxdb:/tmp/restore

docker exec influxdb influxd restore -portable /tmp/restore
**Grafana:**

\# Export dashboards

curl -u admin:grafanapassword \\

&nbsp; http://localhost:3000/api/dashboards/uid/satellite-dashboard \\

&nbsp; > dashboard-backup.json
### Update Services

**Docker Compose:**

\# Pull latest images

docker-compose pull



\# Rebuild and restart

docker-compose up -d --build
**Kubernetes:**

\# Update image

kubectl set image deployment/analyzer \\

&nbsp; analyzer=your-docker-repo/satelliteops-analyzer:v2



\# Rollout status

kubectl rollout status deployment/analyzer



\# Rollback if needed

kubectl rollout undo deployment/analyzer
## 🎯 Performance Tuning

### Analyzer Optimization

Edit .env or K8s secrets:

\# Increase workers for higher throughput

ANALYZER\_WORKERS=8



\# Increase batch size for fewer API calls

ANALYZER\_BATCH\_SIZE=20



\# Increase prefetch for better queue utilization

ANALYZER\_PREFETCH=20
### Kafka Optimization

\# Increase retention for longer history

KAFKA\_RETENTION\_BYTES=1073741824  # 1GB

KAFKA\_RETENTION\_MS=604800000      # 7 days
### InfluxDB Optimization

\# Configure retention policy

docker exec influxdb influx -execute \\

&nbsp; "CREATE RETENTION POLICY telemetry\_30d ON telemetry DURATION 30d REPLICATION 1"
## ✅ Success Criteria

Your deployment is successful when:

1. ✅ All containers/pods are running

2. ✅ Producer sends messages to Kafka topics

3. ✅ Router forwards messages to both telemetry and LLM queues

4. ✅ Telegraf consumes from telemetry queues and writes to InfluxDB

5. ✅ Analyzer consumes from LLM queues and processes batches

6. ✅ LLM insights appear in InfluxDB

7. ✅ Grafana displays real-time data and insights

8. ✅ Prometheus metrics are being collected

9. ✅ No error messages in logs

10. ✅ VSAT producer successfully polls SNMP data

## 🆘 Support

If you encounter issues:

1. **Check logs first**: docker-compose logs or kubectl logs

2. **Verify configuration**: Check .env, config.yaml, secrets

3. **Test connectivity**: Use docker exec to test connections between services

4. **Monitor resources**: Check CPU, memory, disk usage

5. **Review this guide**: Follow troubleshooting steps

## 🎓 Next Steps

1. **Customize dashboards**: Add your own metrics and visualizations

2. **Add alerting**: Configure Prometheus alerts for anomalies

3. **Extend analysis**: Customize LLM prompts for your use case

4. **Add more VSATs**: Update config.yaml with additional VSAT configurations

5. **Implement CI/CD**: Automate builds and deployments

6. **Add authentication**: Secure Grafana, RabbitMQ, and other services

7. **Enable HTTPS**: Configure SSL/TLS for production

**Deployment Date**: {{ 30/12/2025 }}

**Version**: 1.0.0

**Status**: Production Ready ✅
