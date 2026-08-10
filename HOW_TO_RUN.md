# How to Run CompliAssist

This guide will help you get CompliAssist up and running on your local machine for development and testing.

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.9 or higher** - [Download here](https://www.python.org/downloads/)
- **Node.js 16+ and npm** - [Download here](https://nodejs.org/)
- **Git** - [Download here](https://git-scm.com/downloads)
- **Ollama** - [Download here](https://ollama.ai/download)
- **FFmpeg** - [Download here](https://ffmpeg.org/download.html)

### Verify Installations

```bash
# Check Python version
python --version  # Should be 3.9+

# Check Node.js version
node --version    # Should be 16+
npm --version

# Check Git
git --version

# Check Ollama
ollama --version

# Check FFmpeg
ffmpeg -version
```

---

## 🚀 Quick Start (5 Minutes)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/compliasist.git
cd compliasist
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Set Up Ollama

```bash
# Pull the required LLM model
ollama pull mistral

# Verify model is available
ollama list
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file (use your preferred text editor)
# Minimum required configuration:
# LLM_MODEL=mistral:latest
# LLM_BASE_URL=http://localhost:11434
# API_PORT=8000
```

### 5. Initialize Knowledge Base

```bash
# Initialize the system
python initialize_kb.py
```

### 6. Start the Backend

```bash
# Start the API server
python main.py
```

The backend will start on `http://localhost:8000`

### 7. Start the Frontend (New Terminal)

```bash
# Open a new terminal, navigate to the project
cd compliasist

# Activate virtual environment (if needed)
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Navigate to frontend directory
cd "Design Chatbot UI"

# Install frontend dependencies
npm install

# Start frontend development server
npm run dev
```

The frontend will start on `http://localhost:5173`

### 8. Access the Application

- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

---

## 📝 Detailed Setup Instructions

### Backend Setup

#### Step 1: Python Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

#### Step 2: Ollama Configuration

```bash
# Start Ollama service (if not running)
# On macOS/Linux:
ollama serve
# On Windows: Ollama runs as a service automatically

# Pull Mistral model
ollama pull mistral

# Test Ollama
ollama run mistral "Hello, can you help me with compliance?"
```

#### Step 3: Environment Configuration

Create a `.env` file in the root directory:

```env
# LLM Configuration
LLM_MODEL=mistral:latest
LLM_BASE_URL=http://localhost:11434
LLM_TIMEOUT=120
LLM_MAX_TOKENS=512
LLM_TEMPERATURE=0.2

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Embeddings Configuration
EMBEDDINGS_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
FAISS_METRIC=L2

# Retrieval Configuration
TOP_K_DOCUMENTS=5
SIMILARITY_THRESHOLD=0.4
CHUNK_SIZE=500
CHUNK_OVERLAP=100
MIN_CHUNK_LENGTH=50

# Data Paths
DATA_DIR=./Data
DOCUMENTS_DIR=./Data/documents
VECTOR_INDEX_DIR=./Data/vector_index
LOGS_DIR=./logs
```

#### Step 4: Initialize System

```bash
# Run initialization script
python initialize_kb.py

# This will:
# - Create necessary directories
# - Initialize vector store
# - Set up database schemas
# - Create default configurations
```

#### Step 5: Start Backend Server

```bash
# Start the server
python main.py

# You should see output like:
# INFO:     Started server process
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Frontend Setup

#### Step 1: Install Dependencies

```bash
# Navigate to frontend directory
cd "Design Chatbot UI"

# Install Node.js dependencies
npm install

# Or use pnpm for faster installation
pnpm install
```

#### Step 2: Configure Frontend

Create or edit `.env` in the frontend directory:

```env
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=CompliAssist
```

#### Step 3: Start Development Server

```bash
# Start the development server
npm run dev

# The frontend will be available at http://localhost:5173
```

---

## 🧪 Testing the Installation

### Test Backend API

```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","timestamp":"..."}
```

### Test Document Upload

```bash
# Upload a test document
curl -X POST "http://localhost:8000/upload" \
  -F "file=@test_document.pdf" \
  -F "user_id=test_user"

# Expected response:
# {"status":"success","document_id":"...","message":"Document uploaded successfully"}
```

### Test Query

```bash
# Test a compliance query
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the compliance requirements for data storage?",
    "user_id": "test_user",
    "session_id": "test_session"
  }'
```

---

## 📁 Project Structure Overview

```
compliasist/
├── api_server.py              # Main FastAPI application
├── main.py                    # Application entry point
├── config.py                  # Configuration management
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── .gitignore               # Git ignore rules
├── loaders/                 # Document loading modules
├── compliance_*.py          # Compliance enforcement modules
├── video_*.py              # Video processing modules
├── vector_store.py         # FAISS vector database
├── llm_interface.py        # LLM integration
├── Design Chatbot UI/      # React frontend
│   ├── src/               # React source code
│   ├── package.json       # Node.js dependencies
│   └── vite.config.ts     # Vite configuration
├── Data/                  # Data directories
│   ├── documents/        # Uploaded documents
│   ├── vector_index/     # FAISS index files
│   └── sessions/         # Chat sessions
└── logs/                  # Application logs
```

---

## 🔧 Common Tasks

### Upload Documents

**Via API:**
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@your_document.pdf" \
  -F "user_id=your_user_id"
```

**Via Frontend:**
1. Open http://localhost:5173
2. Click "Upload Document" button
3. Select file from your computer
4. Wait for processing confirmation

### Upload Videos

**Via API:**
```bash
curl -X POST "http://localhost:8000/video/upload" \
  -F "file=@your_video.mp4" \
  -F "user_id=your_user_id"
```

**Via Frontend:**
1. Open http://localhost:5173
2. Navigate to Video section
3. Click "Upload Video" button
4. Select video file
5. Wait for transcription and processing

### Manage Sessions

**List all sessions:**
```bash
curl http://localhost:8000/sessions
```

**Delete a session:**
```bash
curl -X DELETE "http://localhost:8000/sessions/{session_id}"
```

### View Logs

```bash
# View application logs
tail -f logs/application.log

# View error logs
tail -f logs/error.log
```

---

## 🐛 Troubleshooting

### Issue: Python Module Not Found

**Solution:**
```bash
# Ensure virtual environment is activated
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Ollama Connection Failed

**Solution:**
```bash
# Check if Ollama is running
ollama list

# Start Ollama service
ollama serve

# Verify model is available
ollama pull mistral
```

### Issue: Port Already in Use

**Solution:**
```bash
# Find process using port 8000
# Windows:
netstat -ano | findstr :8000
# macOS/Linux:
lsof -i :8000

# Kill the process or change port in .env
# Edit .env:
# API_PORT=8001
```

### Issue: Frontend Won't Start

**Solution:**
```bash
# Clear node_modules and reinstall
cd "Design Chatbot UI"
rm -rf node_modules package-lock.json
npm install

# Or use pnpm
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

### Issue: Vector Store Not Found

**Solution:**
```bash
# Reinitialize knowledge base
python initialize_kb.py

# Check if Data directory exists
ls Data/
```

### Issue: FFmpeg Not Found

**Solution:**
```bash
# Install FFmpeg
# Windows: Download from https://ffmpeg.org/download.html
# macOS: brew install ffmpeg
# Ubuntu/Debian: sudo apt-get install ffmpeg

# Verify installation
ffmpeg -version
```

---

## 🔄 Development Workflow

### Making Changes to Backend

1. Edit Python files in the root directory
2. Restart the backend server:
   ```bash
   # Stop server (Ctrl+C)
   # Start again
   python main.py
   ```
3. Test changes via API or frontend

### Making Changes to Frontend

1. Edit React files in `Design Chatbot UI/src/`
2. Vite will automatically hot-reload changes
3. Check browser for updates

### Adding New Dependencies

**Backend:**
```bash
# Add to requirements.txt
pip install new-package
pip freeze > requirements.txt
```

**Frontend:**
```bash
cd "Design Chatbot UI"
npm install new-package
```

---

## 📊 Performance Tips

### Optimize Vector Search

```bash
# Adjust similarity threshold in .env
SIMILARITY_THRESHOLD=0.5  # Higher = more precise, fewer results

# Adjust chunk size for better context
CHUNK_SIZE=1000  # Larger chunks = more context, slower search
```

### Optimize LLM Performance

```bash
# Use smaller models for faster responses
LLM_MODEL=mistral:7b  # Instead of mistral:latest

# Adjust max tokens
LLM_MAX_TOKENS=256  # Shorter responses
```

### Optimize Memory Usage

```bash
# Reduce chunk overlap
CHUNK_OVERLAP=50  # Less memory usage

# Reduce top_k documents
TOP_K_DOCUMENTS=3  # Fewer documents to process
```

---

## 🔒 Security Considerations for Development

### Environment Variables

- Never commit `.env` file to version control
- Use `.env.example` as template
- Keep sensitive data (API keys, passwords) in environment variables

### API Security

- In development, API runs without authentication
- For production, implement authentication middleware
- Use HTTPS in production environments

### Data Privacy

- Uploaded documents are stored locally in development
- Ensure proper data handling in production
- Implement user authentication for multi-user scenarios

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs (when server is running)
- **Architecture Guide**: See `ARCHITECTURE.md`
- **Deployment Guide**: See `DEPLOYMENT.md`
- **Project README**: See `README.md`

---

## 🆘 Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review logs in `logs/` directory
3. Check API documentation at `/docs` endpoint
4. Open an issue on GitHub

---

## ✅ Verification Checklist

Before using CompliAssist, verify:

- [ ] Python 3.9+ installed
- [ ] Virtual environment created and activated
- [ ] All Python dependencies installed
- [ ] Ollama installed and running
- [ ] Mistral model pulled
- [ ] `.env` file configured
- [ ] Knowledge base initialized
- [ ] Backend server running on port 8000
- [ ] Frontend dependencies installed
- [ ] Frontend server running on port 5173
- [ ] Can access http://localhost:5173
- [ ] Can access http://localhost:8000/docs

---

**Congratulations! You're ready to use CompliAssist! 🎉**

For production deployment, see `DEPLOYMENT.md`.
