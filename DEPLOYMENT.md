# CompliAssist Deployment Guide

## 🚀 Deployment Options

CompliAssist can be deployed in multiple environments depending on your needs:

1. **Local Development** - For testing and development
2. **Railway Cloud** - Recommended for production
3. **Docker Container** - For containerized deployments
4. **Traditional VPS** - For custom server deployments

---

## 📋 Prerequisites

### For All Deployments
- Python 3.9 or higher
- Node.js 16+ and npm/pnpm
- Git
- Ollama (for local LLM inference)
- FFmpeg (for video processing)

### For Cloud Deployments
- Cloud provider account (Railway, AWS, GCP, etc.)
- Domain name (optional)
- SSL certificate (optional but recommended)

---

## 🖥️ Local Development Deployment

### Step 1: Environment Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/compliasist.git
cd compliasist

# Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install Ollama (if not already installed)
# Visit: https://ollama.ai/download
# For Linux: curl -fsSL https://ollama.ai/install.sh | sh
# For macOS: brew install ollama
# For Windows: Download from ollama.ai

# Pull required LLM model
ollama pull mistral

# Install FFmpeg (if not already installed)
# Ubuntu/Debian: sudo apt-get install ffmpeg
# macOS: brew install ffmpeg
# Windows: Download from https://ffmpeg.org/download.html
```

### Step 2: Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# Minimum required settings:
# LLM_MODEL=mistral:latest
# LLM_BASE_URL=http://localhost:11434
# API_PORT=8000
```

### Step 3: Initialize Knowledge Base

```bash
# Initialize the knowledge base and vector store
python initialize_kb.py
```

### Step 4: Start Services

```bash
# Terminal 1: Start Backend API
python main.py

# Terminal 2: Start Frontend (in new terminal)
cd "Design Chatbot UI"
npm install
npm run dev
```

### Step 5: Access Application

- **Backend API**: http://localhost:8000
- **Frontend UI**: http://localhost:5173
- **API Documentation**: http://localhost:8000/docs

---

## ☁️ Railway Cloud Deployment

Railway is the recommended platform for deploying CompliAssist due to its simplicity and built-in support for Python and Node.js applications.

### Step 1: Prepare Railway Account

1. Sign up at [railway.app](https://railway.app)
2. Connect your GitHub account
3. Create a new project

### Step 2: Configure Railway Project

```bash
# Install Railway CLI (optional)
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize Railway in project directory
railway init
```

### Step 3: Add Services

**Backend Service:**
```bash
# Add Python backend service
railway add

# Configure build settings
# Railway will automatically detect Python and install requirements.txt
```

**Frontend Service:**
```bash
# Add Node.js frontend service
cd "Design Chatbot UI"
railway add

# Configure build settings
# Railway will automatically detect Node.js and run npm build
```

### Step 4: Set Environment Variables

In Railway dashboard, set these environment variables:

**Backend Variables:**
```
LLM_MODEL=mistral:latest
LLM_BASE_URL=http://localhost:11434
API_PORT=8000
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
PYTHON_VERSION=3.9
```

**Frontend Variables:**
```
VITE_API_URL=https://your-backend-url.railway.app
```

### Step 5: Deploy

```bash
# Deploy to Railway
railway up

# Monitor deployment
railway logs
```

### Step 6: Configure Ollama for Production

For production, you have two options:

**Option A: Use Railway's Ollama Integration**
- Railway supports Ollama as a service
- Add Ollama service to your Railway project
- Update `LLM_BASE_URL` to point to Railway Ollama service

**Option B: External Ollama Server**
- Deploy Ollama on a separate server
- Update `LLM_BASE_URL` to point to your external Ollama server
- Ensure proper network connectivity

### Step 7: Configure Persistent Storage

Railway provides ephemeral storage by default. For persistent data:

1. Add a Railway Volume service
2. Mount volume to `Data/` directory
3. Configure in `railway.json`:

```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "volumes": [
      {
        "path": "Data",
        "name": "compliance-data"
      }
    ]
  }
}
```

---

## 🐳 Docker Deployment

### Step 1: Create Dockerfile

Create `Dockerfile` in the root directory:

```dockerfile
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p Data/documents Data/knowledge_base Data/vector_index Data/sessions logs

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
```

### Step 2: Create Docker Compose File

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./Data:/app/Data
      - ./logs:/app/logs
    environment:
      - LLM_MODEL=mistral:latest
      - LLM_BASE_URL=http://ollama:11434
      - API_PORT=8000
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    command: serve

  frontend:
    build: ./Design Chatbot UI
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000
    depends_on:
      - backend

volumes:
  ollama_data:
```

### Step 3: Build and Run

```bash
# Build and start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## 🖥️ VPS Deployment (Ubuntu/Debian)

### Step 1: Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and Node.js
sudo apt install python3.9 python3-pip nodejs npm git -y

# Install FFmpeg
sudo apt install ffmpeg -y

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull LLM model
ollama pull mistral
```

### Step 2: Deploy Application

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/compliasist.git
cd compliasist

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with production settings

# Initialize knowledge base
python initialize_kb.py
```

### Step 3: Setup Systemd Service

Create `/etc/systemd/system/compliasist.service`:

```ini
[Unit]
Description=CompliAssist Backend Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/compliasist
Environment="PATH=/path/to/compliasist/.venv/bin"
ExecStart=/path/to/compliasist/.venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable compliasist
sudo systemctl start compliasist
sudo systemctl status compliasist
```

### Step 4: Setup Nginx Reverse Proxy

```bash
# Install Nginx
sudo apt install nginx -y

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/compliasist
```

Add this configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /frontend {
        alias /path/to/Design Chatbot UI/dist;
        try_files $uri $uri/ /frontend/index.html;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/compliasist /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 5: Setup SSL with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com
```

---

## 🔧 Configuration Management

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `LLM_MODEL` | Ollama model to use | `mistral:latest` | Yes |
| `LLM_BASE_URL` | Ollama server URL | `http://localhost:11434` | Yes |
| `API_PORT` | API server port | `8000` | No |
| `EMBEDDINGS_MODEL` | Embeddings model | `sentence-transformers/all-MiniLM-L6-v2` | No |
| `SIMILARITY_THRESHOLD` | Document retrieval threshold | `0.4` | No |
| `CHUNK_SIZE` | Document chunk size | `500` | No |

### Production Considerations

1. **Security**
   - Use environment variables for sensitive data
   - Enable HTTPS/SSL
   - Implement rate limiting
   - Use firewall rules

2. **Performance**
   - Use production-grade database (PostgreSQL instead of SQLite)
   - Implement caching (Redis)
   - Use CDN for static assets
   - Enable compression

3. **Monitoring**
   - Set up logging aggregation
   - Monitor system resources
   - Implement health checks
   - Set up alerts

4. **Backup**
   - Regular database backups
   - Document storage backups
   - Vector index backups
   - Configuration backups

---

## 📊 Monitoring and Maintenance

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check service status
sudo systemctl status compliasist
```

### Log Management

```bash
# View application logs
tail -f logs/application.log

# View systemd logs
sudo journalctl -u compliasist -f
```

### Backup Strategy

```bash
# Backup data directory
tar -czf backup-$(date +%Y%m%d).tar.gz Data/

# Backup database
cp document_versions.db backup/document_versions-$(date +%Y%m%d).db
```

---

## 🔄 Updates and Maintenance

### Updating the Application

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl restart compliasist
```

### Database Migrations

```bash
# Backup before migration
cp document_versions.db backup/document_versions-pre-migration.db

# Run migration (if applicable)
python migrate_database.py
```

---

## 🐛 Troubleshooting

### Common Issues

**Issue: Ollama connection failed**
```bash
# Check Ollama status
ollama list

# Restart Ollama
sudo systemctl restart ollama
```

**Issue: Vector store not found**
```bash
# Reinitialize knowledge base
python initialize_kb.py
```

**Issue: Port already in use**
```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>
```

**Issue: Memory errors**
```bash
# Increase swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 📞 Support

For deployment issues:
- Check logs: `logs/application.log`
- Review documentation: `ARCHITECTURE.md`, `HOW_TO_RUN.md`
- Open GitHub issue for persistent problems

---

**Deployment completed successfully! 🎉**
