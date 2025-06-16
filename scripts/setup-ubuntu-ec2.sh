#!/bin/bash

# Email Summarizer - Ubuntu EC2 Setup Script
# This script sets up the complete environment on a fresh Ubuntu EC2 instance

set -e  # Exit on error

echo "=== Email Summarizer EC2 Setup Script ==="
echo "This script will install Docker, Docker Compose, and set up the application"
echo ""

# Update system packages
echo "1. Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install required system packages
echo "2. Installing required system packages..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    python3-pip \
    python3-venv

# Install Docker
echo "3. Installing Docker..."
# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add current user to docker group
echo "4. Adding user to docker group..."
sudo usermod -aG docker $USER

# Install Docker Compose standalone (for compatibility)
echo "5. Installing Docker Compose..."
DOCKER_COMPOSE_VERSION="v2.24.0"
sudo curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create application directory
echo "6. Setting up application directory..."
APP_DIR="/home/$USER/summarize-email"
if [ ! -d "$APP_DIR" ]; then
    echo "Creating application directory at $APP_DIR"
    mkdir -p "$APP_DIR"
fi

cd "$APP_DIR"

# Clone repository (if not already present)
if [ ! -d ".git" ]; then
    echo "7. Cloning repository..."
    echo "Please enter the Git repository URL:"
    read -r GIT_REPO_URL
    git clone "$GIT_REPO_URL" .
else
    echo "7. Repository already exists, pulling latest changes..."
    git pull
fi

# Create .env file from example if it doesn't exist
if [ ! -f ".env" ]; then
    echo "8. Creating .env file..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env file from .env.example"
        echo "IMPORTANT: Please edit .env file with your actual credentials!"
    else
        echo "Creating basic .env file..."
        cat > .env << EOF
# Azure AD App Registration
TENANT_ID=your_tenant_id
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
TARGET_USER_ID=your_target_user_id

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL_NAME=gpt-4o-mini

# LLM Provider
LLM_PROVIDER=openai

# Redis Configuration (Docker internal network)
REDIS_URL=redis://redis:6379/0
CACHE_EXPIRATION_SECONDS=3600

# PostgreSQL Configuration (Docker internal network)
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=email_summarizer
POSTGRES_SERVER=db
POSTGRES_PORT=5432

# Application Settings
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_TIMESCALE=minute
RAG_INGESTION_INTERVAL_HOURS=24
EOF
        echo "Created basic .env file. Please edit it with your actual credentials!"
    fi
fi

# Create data directories
echo "9. Creating data directories..."
mkdir -p data/postgres
mkdir -p data/redis

# Set up systemd service for auto-start
echo "10. Setting up systemd service..."
sudo tee /etc/systemd/system/email-summarizer.service > /dev/null << EOF
[Unit]
Description=Email Summarizer Docker Compose Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
User=$USER
Group=docker

[Install]
WantedBy=multi-user.target
EOF

# Enable the service
sudo systemctl daemon-reload
sudo systemctl enable email-summarizer.service

# Create initialization script
echo "11. Creating initialization script..."
cat > init-services.sh << 'EOF'
#!/bin/bash

echo "Initializing Email Summarizer services..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until docker exec email_summarizer_db pg_isready -U user -d email_summarizer; do
    echo "PostgreSQL is not ready yet. Waiting..."
    sleep 2
done
echo "PostgreSQL is ready!"

# Initialize the database (create tables, extensions, etc.)
echo "Initializing database..."
docker exec email_summarizer_db psql -U user -d email_summarizer -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until docker exec email_summarizer_redis redis-cli ping; do
    echo "Redis is not ready yet. Waiting..."
    sleep 2
done
echo "Redis is ready!"

# Run any database migrations if needed
if [ -f "alembic.ini" ]; then
    echo "Running database migrations..."
    docker exec email_summarizer_api alembic upgrade head
fi

echo "All services initialized successfully!"
EOF

chmod +x init-services.sh

# Create health check script
echo "12. Creating health check script..."
cat > check-health.sh << 'EOF'
#!/bin/bash

echo "=== Email Summarizer Health Check ==="

# Check Docker services
echo -e "\n1. Docker Services Status:"
docker-compose ps

# Check PostgreSQL
echo -e "\n2. PostgreSQL Status:"
docker exec email_summarizer_db pg_isready -U user -d email_summarizer && echo "PostgreSQL is healthy" || echo "PostgreSQL is not responding"

# Check Redis
echo -e "\n3. Redis Status:"
docker exec email_summarizer_redis redis-cli ping && echo "Redis is healthy" || echo "Redis is not responding"

# Check API
echo -e "\n4. API Status:"
curl -s http://localhost:8000/health | jq . || echo "API is not responding"

# Check disk usage
echo -e "\n5. Disk Usage:"
df -h | grep -E "^/dev/"

# Check memory usage
echo -e "\n6. Memory Usage:"
free -h

echo -e "\n=== Health check complete ==="
EOF

chmod +x check-health.sh

# Install monitoring tools
echo "13. Installing monitoring tools..."
sudo apt-get install -y htop iotop nethogs jq

# Set up log rotation
echo "14. Setting up log rotation..."
sudo tee /etc/logrotate.d/email-summarizer > /dev/null << EOF
$APP_DIR/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 $USER $USER
}
EOF

# Create logs directory
mkdir -p logs

# Final instructions
echo ""
echo "=== Setup Complete! ==="
echo ""
echo "Next steps:"
echo "1. Edit the .env file with your actual credentials:"
echo "   nano .env"
echo ""
echo "2. Log out and log back in for Docker group changes to take effect:"
echo "   exit"
echo "   ssh back into your EC2 instance"
echo ""
echo "3. Start the services:"
echo "   cd $APP_DIR"
echo "   docker-compose up -d"
echo ""
echo "4. Initialize the services:"
echo "   ./init-services.sh"
echo ""
echo "5. Check service health:"
echo "   ./check-health.sh"
echo ""
echo "6. View logs:"
echo "   docker-compose logs -f"
echo ""
echo "The application will be available at http://YOUR_EC2_IP:8000"
echo "The API documentation will be at http://YOUR_EC2_IP:8000/docs" 