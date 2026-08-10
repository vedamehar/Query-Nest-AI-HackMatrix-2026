# CompliAssist Architecture Documentation

## 🏗️ System Overview

CompliAssist is a sophisticated AI-powered compliance assistant built on a microservices-inspired architecture. The system combines Retrieval-Augmented Generation (RAG) with enterprise-grade compliance enforcement, video processing capabilities, and a modern React frontend.

## 📐 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         React Frontend                            │
│                    (Material UI + Vite)                          │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/REST API
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Server                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ /ask Endpoint│  │ /upload      │  │ /video/upload│          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│  ┌──────▼─────────────────▼─────────────────▼──────┐           │
│  │           Request Processing Pipeline            │           │
│  └────────────────────────┬────────────────────────┘           │
└───────────────────────────┼─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Compliance   │  │   RAG System  │  │   Video       │
│  Engine       │  │               │  │   Processor   │
│               │  │               │  │               │
│ • Rules       │  │ • Vector Store│  │ • Whisper     │
│ • Formatter   │  │ • Retrieval   │  │ • Transcription│
│ • Validator   │  │ • Embeddings  │  │ • Analysis    │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  Knowledge Base  │
                  │                 │
                  │ • Documents     │
                  │ • FAISS Index   │
                  │ • Graph DB      │
                  │ • Sessions      │
                  └─────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │   LLM Service   │
                  │   (Ollama)      │
                  │                 │
                  │ • Mistral       │
                  │ • Local Inference│
                  └─────────────────┘
```

## 🔧 Core Components

### 1. **Frontend Layer**
- **Technology**: React 18 + Material UI + Vite
- **Responsibilities**: 
  - User interface and interaction
  - Real-time chat interface
  - Document upload management
  - Session management
  - Video upload interface
- **Key Files**: `Design Chatbot UI/src/`

### 2. **API Server Layer**
- **Technology**: FastAPI
- **Responsibilities**:
  - REST API endpoint management
  - Request validation and routing
  - Background task management
  - File upload handling
  - Session management
- **Key Files**: `api_server.py`, `main.py`

### 3. **Compliance Enforcement Engine**
- **Responsibilities**:
  - Enterprise rule enforcement
  - Response formatting and validation
  - Risk assessment
  - Violation detection
- **Key Components**:
  - `compliance_enforcement_pipeline.py` - Main pipeline orchestration
  - `compliance_response_formatter.py` - Structured response formatting
  - `compliance_system_prompt.py` - System prompt management
  - `rules_engine.py` - Business rules processing
  - `rag_grounding_enforcer.py` - RAG response validation

### 4. **RAG (Retrieval-Augmented Generation) System**
- **Responsibilities**:
  - Document ingestion and processing
  - Vector embeddings generation
  - Semantic search and retrieval
  - Context management
- **Key Components**:
  - `vector_store.py` - FAISS vector database management
  - `llm_interface.py` - LLM integration (Ollama)
  - `loaders/` - Document loading modules (PDF, CSV, Markdown, Text)
  - `unified_retriever.py` - Unified retrieval logic
  - `multi_version_retriever.py` - Document version handling

### 5. **Video Processing System**
- **Responsibilities**:
  - Video upload and storage
  - Audio transcription (Whisper)
  - Video content analysis
  - Video registry management
- **Key Components**:
  - `video_integration.py` - Main video integration
  - `video_ingestion.py` - Video processing pipeline
  - `video_manager.py` - Video file management
  - `video_retriever.py` - Video content retrieval

### 6. **Session Management**
- **Responsibilities**:
  - Multi-user session isolation
  - Conversation context tracking
  - Session lifecycle management
  - Cross-session leakage prevention
- **Key Components**:
  - `chat_session_manager.py` - Session state management
  - `system_initialization.py` - System startup and initialization

### 7. **Knowledge Graph Service**
- **Responsibilities**:
  - Document relationship mapping
  - Graph-based navigation
  - Entity relationship tracking
- **Key Components**:
  - `graph_service.py` - Knowledge graph operations

### 8. **Document Processing Pipeline**
- **Responsibilities**:
  - Document versioning
  - Background ingestion
  - Document chunking
  - Metadata extraction
- **Key Components**:
  - `document_version_schema.py` - Version tracking
  - `background_ingestion_worker.py` - Async processing
  - `unified_ingestion.py` - Unified ingestion logic

## 🔄 Data Flow

### Query Processing Flow
1. **User Query** → React Frontend
2. **HTTP Request** → FastAPI Server (`/ask` endpoint)
3. **Session Validation** → Session Manager
4. **Query Classification** → Query Classifier
5. **Context Retrieval** → RAG System (Vector Store)
6. **Compliance Check** → Compliance Engine
7. **LLM Generation** → Ollama Service
8. **Response Formatting** → Compliance Formatter
9. **Final Response** → Frontend Display

### Document Upload Flow
1. **File Upload** → React Frontend
2. **HTTP Request** → FastAPI Server (`/upload` endpoint)
3. **File Validation** → Server Utils
4. **Document Loading** → Loaders (PDF/CSV/MD/Text)
5. **Text Chunking** → Ingestion Pipeline
6. **Embedding Generation** → Sentence Transformers
7. **Vector Indexing** → FAISS Vector Store
8. **Metadata Storage** → Document Version Schema
9. **Completion Response** → Frontend

### Video Processing Flow
1. **Video Upload** → React Frontend
2. **HTTP Request** → FastAPI Server (`/video/upload` endpoint)
3. **File Storage** → Video Manager
4. **Audio Extraction** → FFmpeg
5. **Transcription** → Whisper AI
6. **Text Processing** → Video Ingestion
7. **Vector Indexing** → FAISS Vector Store
8. **Registry Update** → Video Registry
9. **Completion Response** → Frontend

## 🗄️ Data Storage Architecture

### Vector Storage
- **Technology**: FAISS (Facebook AI Similarity Search)
- **Purpose**: High-performance vector similarity search
- **Index Type**: L2 distance metric
- **Dimension**: 384 (MiniLM embeddings)
- **Location**: `Data/vector_index/`

### Document Storage
- **Technology**: File system + SQLite
- **Purpose**: Document versioning and metadata
- **Schema**: Document versions, upload timestamps, user tracking
- **Location**: `Data/documents/`, `document_versions.db`

### Session Storage
- **Technology**: File system (JSON)
- **Purpose**: Chat session persistence and context
- **Isolation**: Complete user/session separation
- **Location**: `Data/sessions/`

### Knowledge Graph
- **Technology**: NetworkX + SQLite
- **Purpose**: Document relationship mapping
- **Storage**: Graph database
- **Location**: `Data/knowledge_graph.db`

## 🔐 Security Architecture

### Session Isolation
- Complete separation of user sessions
- No cross-session data leakage
- Session-specific context management

### Compliance Enforcement
- All responses pass through compliance pipeline
- Automatic violation detection
- Risk level assignment
- Structured output formatting

### Audit Logging
- Comprehensive audit trail
- All compliance decisions logged
- User action tracking
- Document access logging

## ⚡ Performance Optimization

### Vector Search
- FAISS for sub-millisecond retrieval
- Cached embedding models
- Batch processing support

### Background Processing
- Async document ingestion
- Non-blocking API responses
- Progress tracking for uploads

### Caching Strategy
- Embedding model caching
- LLM response caching (optional)
- Session context caching

## 🚀 Scalability Considerations

### Horizontal Scaling
- Stateless API server design
- Shared vector storage (can be moved to cloud)
- Session storage can be externalized (Redis)

### Vertical Scaling
- Efficient memory usage
- Optimized vector operations
- Background task management

## 🔧 Configuration Management

### Environment Variables
- LLM model selection
- API endpoints
- Database paths
- Vector store configuration
- Compliance rule settings

### Configuration File
- Centralized configuration in `config.py`
- Environment-specific settings
- Default values with override capability

## 📊 Monitoring & Observability

### Logging
- Structured logging format
- Audit trail for compliance
- Error tracking and debugging

### Health Checks
- API health endpoint
- Service status monitoring
- Database connectivity checks

## 🔄 Integration Points

### External Services
- **Ollama**: Local LLM inference
- **Whisper**: Video transcription
- **FFmpeg**: Video/audio processing

### Future Integrations
- Cloud vector databases (Pinecone, Weaviate)
- External LLM APIs (OpenAI, Anthropic)
- Enterprise authentication systems
- Document management systems

## 🎯 Design Principles

1. **Modularity**: Clear separation of concerns
2. **Scalability**: Designed for growth
3. **Security**: Compliance-first approach
4. **Performance**: Optimized for speed
5. **Maintainability**: Clean code architecture
6. **Extensibility**: Easy to add new features

This architecture provides a solid foundation for enterprise-grade compliance assistance while maintaining flexibility for future enhancements.
