#!/bin/bash

PROVIDERS=("xai" "openai" "gemini")

for provider in "${PROVIDERS[@]}"; do
    echo "Testing $provider..."
    
    # Set provider
    sed -i "s/LLM_PROVIDER=.*/LLM_PROVIDER=$provider/" .env
    
    # Restart analyzer
    docker compose restart analyzer
    
    # Wait 60 seconds
    echo "Waiting 60 seconds for analysis..."
    sleep 60
    
    # Check logs
    docker logs analyzer | grep "Analysis complete" | tail -3
    
    echo "---"
done

echo "Test complete! Check Grafana for insights from all providers."
