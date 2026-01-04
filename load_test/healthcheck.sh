#!/bin/bash

echo "🔍 SatelliteOps Health Check"
echo "============================"
echo ""

# Check Docker
if docker ps > /dev/null 2>&1; then
    echo "✅ Docker is running"
else
    echo "❌ Docker is not running"
    exit 1
fi

# Check services
RUNNING=$(docker-compose ps | grep "Up" | wc -l)
TOTAL=$(docker-compose ps | tail -n +2 | wc -l)
echo "✅ Services: $RUNNING/$TOTAL running"

# Check provider
PROVIDER=$(docker logs analyzer 2>&1 | grep "LLM Provider:" | tail -1)
echo "✅ $PROVIDER"

# Check API key
if docker logs analyzer 2>&1 | grep "🔑 API Key: ✅" > /dev/null; then
    echo "✅ API key configured"
else
    echo "⚠️  API key not configured"
fi

# Check processing
PROCESSED=$(docker logs analyzer 2>&1 | grep "Analysis complete" | wc -l)
echo "✅ Analyses completed: $PROCESSED"

# Check InfluxDB
INSIGHTS=$(curl -sG 'http://localhost:8086/query?db=telemetry' \
  --data-urlencode "q=SELECT COUNT(*) FROM insights" | \
  grep -o '"value":[0-9]*' | cut -d':' -f2)
echo "✅ Insights in database: $INSIGHTS"

echo ""
echo "============================"
echo "Health check complete!"