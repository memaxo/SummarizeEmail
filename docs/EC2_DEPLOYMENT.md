# EC2 Deployment Guide for Email Summarizer

This guide provides step-by-step instructions for deploying the Email Summarizer application on an Ubuntu EC2 instance.

## Prerequisites

1. An AWS account with EC2 access
2. An EC2 instance running Ubuntu 22.04 LTS or later
3. Security group configured with the following inbound rules:
   - Port 22 (SSH)
   - Port 8000 (API)
   - Port 8089 (Locust UI - optional)
   - Port 5432 (PostgreSQL - only if needed for external access)

## Quick Start

1. **SSH into your EC2 instance:**
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-ip
   ```

2. **Download and run the setup script:**
   ```bash
   curl -O https://raw.githubusercontent.com/YOUR_REPO/main/scripts/setup-ubuntu-ec2.sh
   chmod +x setup-ubuntu-ec2.sh
   ./setup-ubuntu-ec2.sh
   ```

3. **Follow the script prompts and post-installation steps**

## Manual Installation Steps

If you prefer to install manually or need to troubleshoot:

### 1. Update System
```bash
sudo apt-get update
sudo apt-get upgrade -y
```

### 2. Install Docker
```bash
# Install prerequisites
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
```

### 3. Install Docker Compose
```bash
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 4. Clone Repository
```bash
cd ~
git clone YOUR_REPOSITORY_URL summarize-email
cd summarize-email
```

### 5. Configure Environment
```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

Required environment variables:
- `TENANT_ID`: Azure AD tenant ID
- `CLIENT_ID`: Azure AD application ID
- `CLIENT_SECRET`: Azure AD application secret
- `TARGET_USER_ID`: Target user's ID for email access
- `OPENAI_API_KEY`: OpenAI API key

### 6. Start Services
```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

### 7. Initialize Database
```bash
# Wait for services to be ready
./scripts/init-services.sh

# Or manually:
docker exec email_summarizer_db psql -U user -d email_summarizer -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Service Management

### Starting Services
```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d redis db summarizer-api
```

### Stopping Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Viewing Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f summarizer-api
```

### Health Checks
```bash
# Run health check script
./check-health.sh

# Manual checks
curl http://localhost:8000/health
docker exec email_summarizer_redis redis-cli ping
docker exec email_summarizer_db pg_isready -U user
```

## Monitoring

### System Resources
```bash
# CPU and Memory
htop

# Disk usage
df -h

# Network connections
sudo netstat -tlnp

# Docker stats
docker stats
```

### Application Metrics
- Prometheus metrics: `http://your-ec2-ip:8000/metrics`
- API documentation: `http://your-ec2-ip:8000/docs`
- Locust load testing: `http://your-ec2-ip:8089`

## Troubleshooting

### Common Issues

1. **Docker permission denied:**
   ```bash
   # Log out and back in after adding user to docker group
   exit
   # SSH back in
   ```

2. **Port already in use:**
   ```bash
   # Find process using port
   sudo lsof -i :8000
   # Kill process if needed
   sudo kill -9 <PID>
   ```

3. **Database connection issues:**
   ```bash
   # Check PostgreSQL logs
   docker logs email_summarizer_db
   # Restart database
   docker-compose restart db
   ```

4. **Redis connection issues:**
   ```bash
   # Check Redis logs
   docker logs email_summarizer_redis
   # Test Redis connection
   docker exec email_summarizer_redis redis-cli ping
   ```

### Debugging

1. **Check service logs:**
   ```bash
   docker-compose logs summarizer-api | tail -100
   ```

2. **Access container shell:**
   ```bash
   docker exec -it email_summarizer_api /bin/bash
   ```

3. **Check environment variables:**
   ```bash
   docker exec email_summarizer_api env | grep -E "(REDIS|POSTGRES|DB_)"
   ```

## Security Considerations

1. **Firewall Configuration:**
   ```bash
   # Allow only necessary ports
   sudo ufw allow 22/tcp
   sudo ufw allow 8000/tcp
   sudo ufw enable
   ```

2. **SSL/TLS Setup:**
   - Use a reverse proxy (nginx) with Let's Encrypt
   - Or use AWS Application Load Balancer with ACM certificate

3. **Secrets Management:**
   - Use AWS Secrets Manager for production
   - Never commit .env files to git
   - Rotate credentials regularly

## Backup and Recovery

### Backup PostgreSQL
```bash
# Create backup
docker exec email_summarizer_db pg_dump -U user email_summarizer > backup_$(date +%Y%m%d).sql

# Restore backup
docker exec -i email_summarizer_db psql -U user email_summarizer < backup_20240101.sql
```

### Backup Redis
```bash
# Redis automatically saves to /data/dump.rdb
# Copy backup
docker cp email_summarizer_redis:/data/dump.rdb redis_backup_$(date +%Y%m%d).rdb
```

## Performance Tuning

1. **PostgreSQL Configuration:**
   - Adjust shared_buffers based on available RAM
   - Configure max_connections based on load

2. **Redis Configuration:**
   - Set maxmemory policy
   - Configure persistence settings

3. **API Configuration:**
   - Adjust worker count in Dockerfile
   - Configure rate limiting in .env

## Maintenance

### Regular Tasks
1. Monitor disk space
2. Check logs for errors
3. Update dependencies
4. Backup data
5. Review security groups

### Updates
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## Support

For issues or questions:
1. Check application logs
2. Review this documentation
3. Check GitHub issues
4. Contact support team 