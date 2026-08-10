"""
System Initialization: Dependency injection for GuardedRetrievalPipeline.

This module properly initializes all system dependencies in correct order,
then injects them into the pipeline.

Order matters:
1. LLMController (tests Ollama connectivity)
2. AuditLogger (creates audit DB)
3. RuleEngine (loads compliance registries)
4. EmbeddingModel + VectorStore (loads vector index)
5. SemanticRetriever (combines VectorStore + EmbeddingModel)
6. GuardedRetrievalPipeline (final assembly)
"""

from pathlib import Path
import config
from rules_engine import RuleEngine
from vector_store import SemanticRetriever, VectorStore, EmbeddingModel
from llm_interface import LLMController
from audit_logger import AuditLogger


def initialize_system():
    """
    Initialize all system components and return fully assembled pipeline.
    
    Returns:
        GuardedRetrievalPipeline: Production-ready pipeline with all dependencies
        
    Raises:
        RuntimeError: If any component fails to initialize
        ImportError: If required packages are missing
    """
    print("\n" + "="*70)
    print("         SYSTEM INITIALIZATION - DEPENDENCY INJECTION")
    print("="*70)
    
    try:
        # ========== STEP 1: Initialize LLMController ==========
        print("\n[1/6] Initializing LLMController...")
        print(f"      Model: {config.LLM_MODEL}")
        print(f"      URL: {config.LLM_BASE_URL}")
        try:
            llm_controller = LLMController(
                model_name=config.LLM_MODEL,
                base_url=config.LLM_BASE_URL,
                timeout=config.LLM_TIMEOUT,
                temperature=config.LLM_TEMPERATURE
            )
            print("      ✓ LLMController initialized")
            print("      ✓ Ollama connectivity verified")
            print("      ✓ Model availability verified")
        except Exception as e:
            raise RuntimeError(f"LLMController initialization failed: {str(e)}")
        
        # ========== STEP 2: Initialize AuditLogger ==========
        print("\n[2/6] Initializing AuditLogger...")
        print(f"      DB Path: {config.AUDIT_DB_PATH}")
        try:
            audit_logger = AuditLogger(db_path=config.AUDIT_DB_PATH)
            print("      ✓ AuditLogger initialized")
            print("      ✓ Audit database schema created")
        except Exception as e:
            raise RuntimeError(f"AuditLogger initialization failed: {str(e)}")
        
        # ========== STEP 3: Initialize RuleEngine ==========
        print("\n[3/6] Initializing RuleEngine...")
        print(f"      Restricted CSV: {Path(config.RESTRICTED_ENTITIES_CSV).name}")
        print(f"      Approved CSV: {Path(config.APPROVED_ALTERNATIVES_CSV).name}")
        try:
            rule_engine = RuleEngine(
                restricted_csv=config.RESTRICTED_ENTITIES_CSV,
                approved_csv=config.APPROVED_ALTERNATIVES_CSV
            )
            print("      ✓ RuleEngine initialized")
            print(f"      ✓ Loaded {len(rule_engine.restricted_entities)} restricted entities")
            print(f"      ✓ Loaded {len(rule_engine.approved_entities)} approved entities")
        except Exception as e:
            raise RuntimeError(f"RuleEngine initialization failed: {str(e)}")
        
        # ========== STEP 4: Initialize Embedding Model ==========
        print("\n[4/6] Initializing EmbeddingModel...")
        print(f"      Model: {config.EMBEDDINGS_MODEL}")
        print(f"      Dimension: {config.EMBEDDING_DIMENSION}")
        try:
            embedding_model = EmbeddingModel(
                model_name=config.EMBEDDINGS_MODEL
            )
            print("      ✓ EmbeddingModel initialized")
            print("      ✓ Sentence-transformers loaded")
        except Exception as e:
            raise RuntimeError(f"EmbeddingModel initialization failed: {str(e)}")
        
        # ========== STEP 5: Initialize VectorStore + SemanticRetriever ==========
        print("\n[5/6] Initializing VectorStore & SemanticRetriever...")
        print(f"      Index Path: {config.FAISS_INDEX_FILE}")
        print(f"      Top-K: {config.TOP_K_DOCUMENTS}")
        try:
            vector_store = VectorStore(
                embedding_dim=config.EMBEDDING_DIMENSION,
                index_path=config.FAISS_INDEX_FILE
            )
            # ✅ Load existing FAISS index OR create new one if it doesn't exist
            try:
                vector_store.load(config.FAISS_INDEX_FILE)
                print(f"      ✓ VectorStore loaded from disk")
                print(f"      ✓ FAISS index contains {len(vector_store.metadata)} documents")
            except Exception as load_err:
                print(f"      ⚠️  FAISS index not found or corrupted: {str(load_err)[:100]}")
                print(f"      ✓ Creating fresh FAISS index...")
                vector_store.initialize_index()
                print(f"      ✓ Fresh FAISS index created")
            
            semantic_retriever = SemanticRetriever(
                vector_store=vector_store,
                embedding_model=embedding_model
            )
            print("      ✓ SemanticRetriever initialized")
        except Exception as e:
            raise RuntimeError(f"VectorStore/SemanticRetriever initialization failed: {str(e)}")
        
        # ========== STEP 6: Assemble GuardedRetrievalPipeline ==========
        print("\n[6/6] Assembling GuardedRetrievalPipeline...")
        try:
            from pipeline import GuardedRetrievalPipeline
            
            pipeline = GuardedRetrievalPipeline(
                rule_engine=rule_engine,
                retriever=semantic_retriever,
                llm_controller=llm_controller,
                audit_logger=audit_logger
            )
            print("      ✓ GuardedRetrievalPipeline assembled")
            print("      ✓ All dependencies injected successfully")
        except Exception as e:
            raise RuntimeError(f"GuardedRetrievalPipeline assembly failed: {str(e)}")
        
        # ========== INITIALIZATION COMPLETE ==========
        print("\n" + "="*70)
        print("         ✓ SYSTEM FULLY INITIALIZED & READY")
        print("="*70)
        print("\nSystem Components:")
        print("  ✓ Compliance Engine (RuleEngine)")
        print("  ✓ Vector Search (SemanticRetriever)")
        print("  ✓ LLM Interface (LLMController with Ollama)")
        print("  ✓ Audit Trail (AuditLogger)")
        print("  ✓ Full Pipeline (GuardedRetrievalPipeline)")
        print("\n" + "="*70 + "\n")
        
        return pipeline
    
    except RuntimeError as e:
        print(f"\n✗ INITIALIZATION FAILED")
        print(f"  {str(e)}\n")
        raise
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR DURING INITIALIZATION")
        print(f"  {str(e)}\n")
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"Unexpected initialization error: {str(e)}")


if __name__ == "__main__":
    # Test initialization standalone
    try:
        pipeline = initialize_system()
        print("\n✓ Pipeline ready for use!")
        print(f"  Pipeline type: {type(pipeline).__name__}")
    except Exception as e:
        print(f"\n✗ Initialization test failed: {str(e)}")
        exit(1)
