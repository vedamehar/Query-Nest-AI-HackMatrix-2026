"""
LLM Interface: Controlled access to local models via Ollama.
Enforces system prompt, prevents hallucination.
"""
from typing import List, Dict, Any, Optional
import json
import re


class LLMController:
    """Wrapper for controlled LLM access."""
    
    def __init__(self, 
                 model_name: str = "mistral:latest",
                 base_url: str = "http://localhost:11434",
                 timeout: int = 120,
                 temperature: float = 0.2):
        self.model_name = model_name
        self.base_url = base_url
        self.timeout = timeout
        self.temperature = temperature
        self.requests = None
        
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("requests required: pip install requests")
        
        # ✅ Test connectivity on init
        self._test_ollama_connectivity()
        self._validate_model_exists()
    
    def _test_ollama_connectivity(self):
        """Test if Ollama is running and reachable."""
        try:
            print(f"[LLM] Testing Ollama connectivity at {self.base_url}...")
            response = self.requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            response.raise_for_status()
            print(f"[LLM] ✓ Ollama is reachable")
        except Exception as e:
            error_msg = f"Ollama not reachable at {self.base_url}: {str(e)}"
            print(f"[LLM] ✗ {error_msg}")
            raise RuntimeError(error_msg)
    
    def _validate_model_exists(self):
        """Validate that the specified model exists in Ollama."""
        try:
            print(f"[LLM] Checking if model '{self.model_name}' exists...")
            response = self.requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            response.raise_for_status()
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            
            # Check for exact match or base name match
            if self.model_name not in model_names:
                # Try matching base name (e.g., "mistral" for "mistral:latest")
                base_name = self.model_name.split(":")[0]
                matching = [m for m in model_names if m.startswith(base_name)]
                if matching:
                    print(f"[LLM] ⚠️  Model '{self.model_name}' not found, but found: {matching[0]}")
                    print(f"[LLM] Available models: {model_names}")
                else:
                    error_msg = f"Model '{self.model_name}' not found. Available: {model_names}"
                    print(f"[LLM] ✗ {error_msg}")
                    raise RuntimeError(error_msg)
            else:
                print(f"[LLM] ✓ Model '{self.model_name}' is available")
        except Exception as e:
            error_msg = f"Failed to validate model: {str(e)}"
            print(f"[LLM] ✗ {error_msg}")
            raise RuntimeError(error_msg)
    
    def generate(self,
                 system_prompt: str,
                 user_message: str,
                 context: str = "",
                 max_tokens: int = 512,
                 retrieved_docs: Optional[List[Dict]] = None) -> str:
        """Generate response with enforced system prompt and context.
        
        Handles:
        - Prompt length validation and truncation
        - Automatic context reduction if prompt too long
        - Explicit Ollama options (num_ctx, num_predict)
        - Retry logic with smaller context on failure
        - Graceful error handling
        """
        
        # ===== STEP 1: Calculate token estimates =====
        estimated_tokens = self._estimate_tokens(system_prompt, user_message, context)
        print(f"\n[LLM] Estimated tokens: {estimated_tokens}")
        print(f"[LLM] Token estimate breakdown:")
        print(f"      System prompt: {len(system_prompt) // 4} tokens")
        print(f"      User message: {len(user_message) // 4} tokens")
        print(f"      Context: {len(context) // 4} tokens")
        
        # ===== STEP 2: Check if context needs truncation =====
        if estimated_tokens > 8000:
            print(f"[LLM] ⚠️  WARNING: Prompt too long ({estimated_tokens} tokens)")
            print(f"[LLM] Reducing context...")
            context = self._reduce_context(context, retrieved_docs)
            print(f"[LLM] Context reduced to {len(context)} chars")
            estimated_tokens = self._estimate_tokens(system_prompt, user_message, context)
            print(f"[LLM] New token estimate: {estimated_tokens}")
        
        # ===== STEP 3: Build prompt =====
        full_prompt = self._build_prompt(system_prompt, user_message, context)
        
        print(f"\n[LLM] Generating response...")
        print(f"[LLM] Prompt length: {len(full_prompt)} chars")
        print(f"[LLM] Model: {self.model_name}")
        print(f"[LLM] Timeout: {self.timeout}s")
        print(f"[LLM] Temperature: {self.temperature}")
        
        # ===== STEP 4: Generate with Ollama =====
        try:
            response = self._call_ollama(full_prompt, max_tokens, num_ctx=4096)
            return response
        except RuntimeError as e:
            # Retry with smaller context
            if "500" in str(e) or "timeout" in str(e).lower():
                print(f"\n[LLM] ⚠️  First attempt failed, retrying with smaller context...")
                
                # Reduce context more aggressively
                context_minimal = self._reduce_context(context, retrieved_docs, max_chunks=1)
                full_prompt = self._build_prompt(system_prompt, user_message, context_minimal)
                
                print(f"[LLM] Retrying with minimal context ({len(full_prompt)} chars)")
                try:
                    response = self._call_ollama(full_prompt, max_tokens, num_ctx=2048)
                    return response
                except RuntimeError as e2:
                    print(f"[LLM] ✗ Retry also failed: {str(e2)}")
                    raise
            else:
                raise
    
    def _estimate_tokens(self, system_prompt: str, user_message: str, context: str) -> int:
        """Estimate token count (1 token ≈ 4 characters)."""
        total_chars = len(system_prompt) + len(user_message) + len(context)
        return total_chars // 4
    
    def _reduce_context(self, context: str, retrieved_docs: Optional[List[Dict]] = None, 
                       max_chunks: int = 3) -> str:
        """Reduce context by keeping only top documents."""
        if not context:
            return context
        
        if not retrieved_docs or len(retrieved_docs) <= max_chunks:
            return context
        
        print(f"[LLM] Keeping only top {max_chunks} documents (was {len(retrieved_docs)})")
        
        # Keep top N documents
        top_docs = retrieved_docs[:max_chunks]
        reduced_context = "\n---\n".join([
            f"Source: {doc.get('source', 'Unknown')}\n{doc.get('content', '')}"
            for doc in top_docs
        ])
        
        return reduced_context
    
    def _call_ollama(self, prompt: str, max_tokens: int, num_ctx: int = 4096) -> str:
        """Call Ollama API with explicit options and error handling."""
        try:
            print(f"[LLM] Calling {self.base_url}/api/generate...")
            print(f"[LLM]   num_ctx: {num_ctx}")
            print(f"[LLM]   num_predict: {max_tokens}")
            
            # Build request with explicit options
            request_payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_ctx": num_ctx,
                    "num_predict": max_tokens,
                    "top_k": 40,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1
                }
            }
            
            print(f"[LLM]   Sending request...")
            response = self.requests.post(
                f"{self.base_url}/api/generate",
                json=request_payload,
                timeout=self.timeout
            )
            
            print(f"[LLM] Response status: {response.status_code}")
            
            # ===== Handle 500 errors specially =====
            if response.status_code == 500:
                print(f"[LLM] ✗ Ollama returned 500 error")
                print(f"[LLM] Possible causes:")
                print(f"      1. Prompt too long (even with options)")
                print(f"      2. Memory exhaustion")
                print(f"      3. Model crash")
                print(f"[LLM] Response body: {response.text[:500]}")
                raise RuntimeError(f"Ollama 500 error: Internal server error")
            
            response.raise_for_status()
            
            response_json = response.json()
            print(f"[LLM] Response JSON keys: {list(response_json.keys())}")
            
            llm_response = response_json.get("response", "").strip()
            
            if not llm_response:
                error_msg = "Ollama returned empty response"
                print(f"[LLM] ✗ {error_msg}")
                print(f"[LLM] Full response: {response_json}")
                raise RuntimeError(error_msg)
            
            print(f"[LLM] ✓ Response generated ({len(llm_response)} chars)")
            print(f"[LLM] Response preview: {llm_response[:100]}...")
            
            return llm_response
            
        except self.requests.exceptions.Timeout:
            error_msg = f"Ollama request timed out after {self.timeout}s"
            print(f"[LLM] ✗ {error_msg}")
            raise RuntimeError(error_msg)
        except self.requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to Ollama at {self.base_url}: {str(e)}"
            print(f"[LLM] ✗ {error_msg}")
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"LLM generation failed: {str(e)}"
            print(f"[LLM] ✗ {error_msg}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(error_msg)
    
    def _build_prompt(self, system_prompt: str, user_message: str, context: str) -> str:
        """Build the full prompt with system instructions and context."""
        parts = [
            system_prompt,
            "",
            "RETRIEVED DOCUMENTS:",
            context if context else "(No relevant documents found)",
            "",
            "USER QUESTION:",
            user_message,
            "",
            "RESPONSE (cite sources):"
        ]
        return "\n".join(parts)
    
    def extract_citations(self, response: str) -> List[str]:
        """Extract document citations from response."""
        citation_pattern = r'\[([^\]]+)\]|\(([^)]+)\)'
        matches = re.findall(citation_pattern, response)
        citations = [m[0] or m[1] for m in matches]
        return list(set(citations))


class ResponseValidator:
    """Validate LLM responses for grounding and citations."""
    
    @staticmethod
    def validate(response: str, 
                 retrieved_docs: List[Dict[str, Any]],
                 llm_controller: LLMController) -> Dict[str, Any]:
        """Validate response follows structured compliance format."""
        
        validation = {
            "is_valid": True,
            "issues": [],
            "citations_found": [],
            "has_required_sections": True,
            "format_compliant": True
        }
        
        # Check for required sections
        required_sections = [
            "COMPLIANCE STATUS",
            "VIOLATIONS IDENTIFIED",
            "RISK LEVEL",
            "REQUIRED CORRECTIONS",
            "FULLY REWRITTEN COMPLIANT VERSION",
            "POLICY REFERENCES",
            "REFERENCE LINKS"
        ]
        
        response_upper = response.upper()
        missing_sections = []
        
        for section in required_sections:
            if section not in response_upper and section != "VIOLATIONS IDENTIFIED":
                missing_sections.append(section)
        
        if missing_sections and "no approved reference found" not in response.lower():
            validation["has_required_sections"] = False
            validation["issues"].append(f"Missing sections: {', '.join(missing_sections)}")
            validation["format_compliant"] = False
        
        # Check for violations not in bullet format
        if "VIOLATIONS" in response_upper and "•" not in response:
            if "violation" in response.lower() and "- " not in response:
                validation["issues"].append("Violations must use bullet points (•)")
                validation["format_compliant"] = False
        
        # Check for one-paragraph format (naive check)
        paragraphs = response.split("\n\n")
        if len(paragraphs) == 1 and "COMPLIANCE STATUS" not in response:
            validation["issues"].append("Response appears to be single paragraph - must use structured format")
            validation["format_compliant"] = False
        
        # Extract citations
        extracted_citations = llm_controller.extract_citations(response)
        doc_names = set([doc.get("doc_name") for doc in retrieved_docs])
        
        for citation in extracted_citations:
            if citation in doc_names:
                validation["citations_found"].append(citation)
        
        validation["is_valid"] = validation["format_compliant"] and validation["has_required_sections"]
        
        return validation
