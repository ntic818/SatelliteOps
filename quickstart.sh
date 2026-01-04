#!/bin/bash

###############################################################################
# SatelliteOps Quick Start Script
# This script automates the deployment and verification of the SatelliteOps system
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "  $1"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check Docker
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | cut -d ' ' -f3 | cut -d ',' -f1)
        log_success "Docker found: $DOCKER_VERSION"
    else
        log_error "Docker not found. Please install Docker first."
        exit 1
    fi
    
    # Check Docker Compose
    if command -v docker compose &> /dev/null; then
        COMPOSE_VERSION=$(docker compose --version | cut -d ' ' -f4 | cut -d ',' -f1)
        log_success "Docker Compose found: $COMPOSE_VERSION"
    else
        log_error "Docker Compose not found. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if docker info &> /dev/null; then
        log_success "Docker daemon is running"
    else
        log_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi
}

# Check and configure API key
check_api_key() {
    print_header "API Key Configuration"
    
    if [ -f .env ]; then
        if grep -q "XAI_API_KEY=your_xai_api_key" .env || ! grep -q "XAI_API_KEY=" .env; then
            log_warning "xAI API key not configured in .env file"
            echo ""
            echo "Please enter your xAI API key (get it from https://x.ai/api):"
            read -r XAI_KEY
            
            if [ -z "$XAI_KEY" ]; then
                log_error "API key cannot be empty"
                exit 1
            fi
            
            # Update .env file
            if grep -q "XAI_API_KEY=" .env; then
                sed -i.bak "s/XAI_API_KEY=.*/XAI_API_KEY=$XAI_KEY/" .env
            else
                echo "XAI_API_KEY=$XAI_KEY" >> .env
            fi
            
            log_success "API key configured in .env file"
        else
            log_success "xAI API key already configured"
        fi
    else
        log_error ".env file not found. Please create it from .env.example"
        exit 1
    fi
}

# Build Docker images
build_images() {
    print_header "Building Docker Images"
    
    log_info "Building producer image..."
    docker compose build producer
    log_success "Producer built"
    
    log_info "Building router image..."
    docker compose build router
    log_success "Router built"
    
    log_info "Building analyzer image..."
    docker compose build analyzer
    log_success "Analyzer built"
}

# Start services
start_services() {
    print_header "Starting Services"
    
    log_info "Starting infrastructure services (Kafka, RabbitMQ, InfluxDB)..."
    docker compose up -d zookeeper kafka rabbitmq influxdb
    
    log_info "Waiting for infrastructure to be ready (30s)..."
    sleep 30
    
    log_info "Starting Telegraf and Grafana..."
    docker compose up -d telegraf grafana
    
    log_info "Starting application services..."
    docker compose up -d producer vsat_producer router analyzer
    
    log_info "Starting monitoring services..."
    docker compose up -d prometheus node_exporter kafka_exporter rabbitmq_exporter
    
    log_success "All services started"
}

# Wait for services
wait_for_services() {
    print_header "Waiting for Services to Initialize"
    
    log_info "Waiting for services to be healthy (60s)..."
    
    # Wait for RabbitMQ
    for i in {1..30}; do
        if curl -s -u user:password http://localhost:15672/api/overview > /dev/null 2>&1; then
            log_success "RabbitMQ is ready"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for InfluxDB
    for i in {1..30}; do
        if curl -s http://localhost:8086/ping > /dev/null 2>&1; then
            log_success "InfluxDB is ready"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Wait for Grafana
    for i in {1..30}; do
        if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
            log_success "Grafana is ready"
            break
        fi
        echo -n "."
        sleep 2
    done
}

# Verify deployment
verify_deployment() {
    print_header "Verifying Deployment"
    
    # Check all containers are running
    log_info "Checking container status..."
    RUNNING=$(docker compose ps | grep "Up" | wc -l)
    TOTAL=$(docker compose ps | tail -n +2 | wc -l)
    
    if [ "$RUNNING" -eq "$TOTAL" ]; then
        log_success "All $TOTAL containers are running"
    else
        log_warning "$RUNNING out of $TOTAL containers are running"
        docker compose ps
    fi
    
    # Check producer is sending messages
    log_info "Checking producer output..."
    if docker logs producer 2>&1 | grep -q "Sent to"; then
        log_success "Producer is sending messages"
    else
        log_warning "Producer may not be sending messages yet"
    fi
    
    # Check router is routing
    log_info "Checking router output..."
    if docker logs router 2>&1 | grep -q "Routed to"; then
        log_success "Router is routing messages"
    else
        log_warning "Router may not be routing messages yet"
    fi
    
    # Check analyzer is processing
    log_info "Checking analyzer output..."
    if docker logs analyzer 2>&1 | grep -q "Starting worker"; then
        log_success "Analyzer workers started"
    else
        log_warning "Analyzer may not be running yet"
    fi
    
    # Check RabbitMQ queues
    log_info "Checking RabbitMQ queues..."
    QUEUE_COUNT=$(curl -s -u user:password http://localhost:15672/api/queues 2>/dev/null | grep -o '"name"' | wc -l)
    if [ "$QUEUE_COUNT" -gt 0 ]; then
        log_success "Found $QUEUE_COUNT RabbitMQ queues"
    else
        log_warning "No RabbitMQ queues found"
    fi
    
    # Check InfluxDB
    log_info "Checking InfluxDB data..."
    sleep 5  # Give time for data to arrive
    MEASUREMENTS=$(curl -sG 'http://localhost:8086/query?db=telemetry' \
        --data-urlencode "q=SHOW MEASUREMENTS" 2>/dev/null | grep -o '"name"' | wc -l)
    if [ "$MEASUREMENTS" -gt 0 ]; then
        log_success "InfluxDB has $MEASUREMENTS measurements"
    else
        log_warning "No measurements in InfluxDB yet (may need more time)"
    fi
}

# Display access information
show_access_info() {
    print_header "Access Information"
    
    echo ""
    echo "🌐 Web Interfaces:"
    echo "   Grafana:    http://localhost:3000     (admin / grafanapassword)"
    echo "   RabbitMQ:   http://localhost:15672    (user / password)"
    echo "   Prometheus: http://localhost:9090     (no auth)"
    echo ""
    echo "📊 Quick Commands:"
    echo "   View logs:           docker compose logs -f"
    echo "   Check status:        docker compose ps"
    echo "   Stop services:       docker compose down"
    echo "   View producer logs:  docker logs -f producer"
    echo "   View analyzer logs:  docker logs -f analyzer"
    echo ""
    echo "🔍 Verification:"
    echo "   Check queues:  curl -u user:password http://localhost:15672/api/queues | jq"
    echo "   Query data:    curl -G 'http://localhost:8086/query?db=telemetry' \\"
    echo "                       --data-urlencode 'q=SELECT * FROM insights LIMIT 5'"
    echo ""
}

# Show logs
show_logs() {
    print_header "Service Logs (Press Ctrl+C to exit)"
    
    sleep 2
    docker compose logs -f --tail=50
}

# Main menu
show_menu() {
    echo ""
    echo "What would you like to do?"
    echo "  1) Full deployment (build, start, verify)"
    echo "  2) Start services only (already built)"
    echo "  3) Stop services"
    echo "  4) View logs"
    echo "  5) Verify deployment"
    echo "  6) Clean up (remove all containers and volumes)"
    echo "  7) Exit"
    echo ""
    read -p "Enter choice [1-7]: " choice
    
    case $choice in
        1)
            check_prerequisites
            check_api_key
            build_images
            start_services
            wait_for_services
            verify_deployment
            show_access_info
            read -p "Would you like to view logs? (y/n): " view_logs
            if [[ "$view_logs" == "y" || "$view_logs" == "Y" ]]; then
                show_logs
            fi
            ;;
        2)
            check_prerequisites
            start_services
            wait_for_services
            verify_deployment
            show_access_info
            ;;
        3)
            print_header "Stopping Services"
            docker compose down
            log_success "All services stopped"
            ;;
        4)
            show_logs
            ;;
        5)
            verify_deployment
            ;;
        6)
            print_header "Cleaning Up"
            read -p "This will remove all containers and volumes. Continue? (y/n): " confirm
            if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
                docker compose down -v
                log_success "All containers and volumes removed"
            else
                log_info "Cleanup cancelled"
            fi
            ;;
        7)
            log_info "Goodbye!"
            exit 0
            ;;
        *)
            log_error "Invalid choice"
            show_menu
            ;;
    esac
}

# Main execution
main() {
    clear
    cat << "EOF"
    ____        __       ____  _ __       ____          
   / __/____ _ / /_ ___ / / / (_) /_____ / __ \___  ___
  _\ \ / _ `// __// -_) / /_/ / / __/ -_) /_/ / _ \/ _ \
 /___/ \_,_/ \__/ \__/_/\____/_/\__/\__/\____/ .__/\___/
                                             /_/         
EOF
    
    echo ""
    echo "       Intelligent Satellite Telemetry Platform"
    echo "       =========================================="
    echo ""
    
    if [ "$1" == "--auto" ]; then
        # Automated deployment
        check_prerequisites
        check_api_key
        build_images
        start_services
        wait_for_services
        verify_deployment
        show_access_info
    else
        # Interactive menu
        show_menu
    fi
}

# Run main
main "$@"