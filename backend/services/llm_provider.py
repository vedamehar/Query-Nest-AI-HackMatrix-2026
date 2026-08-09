from enum import Enum
import json
import logging
import anthropic
import google.generativeai as genai
import asyncio
from typing import Any
from schemas.chat import ChatbotResponse
from database import get_api_key
from config import settings

log = logging.getLogger("sitesense.llm")

# Valid model names for Gemini (including 2.x family)
GEMINI_VARIANTS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash-lite",
]

class LLMProvider(str, Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"

AVAILABLE_MODELS = {
    "claude": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307"
    ],
    "gemini": [
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ],
    "openrouter": [
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "meta-llama/llama-3-8b-instruct"
    ]
}

def get_available_models() -> dict:
    return AVAILABLE_MODELS

async def get_provider_api_key(provider: str, user_id: str) -> str:
    """
    Retrieve the configured API key for a provider.
    Priority: 
    1. User-specific database key (if user_id is a UUID)
    2. Global environment variables (if user_id is 'system' or no DB key)
    """
    key = None
    
    # 1. Check database if user_id is provided
    if user_id and user_id != "system":
        key = await get_api_key(user_id, provider)

    # 2. Map provider to setting name and check environment variables if no db key
    if not key:
        setting_map = {
            LLMProvider.GEMINI: "GEMINI_API_KEY",
            LLMProvider.CLAUDE: "ANTHROPIC_API_KEY",
            LLMProvider.OPENROUTER: "OPENROUTER_API_KEY"
        }
        
        setting_name = setting_map.get(provider)
        if setting_name:
            key = getattr(settings, setting_name, None)

    if not key:
        raise ValueError(
            f"No API key configured for provider: {provider}. "
            f"Please set your {provider.upper()}_API_KEY in Railway environment variables."
        )
    return key

async def generate_structured_response(
    system_prompt: str,
    user_prompt: str,
    provider: str,
    model: str,
    user_id: str,
    response_schema: type,
    context: str = ""
) -> tuple[dict, int]:
    """
    Generates structured response from any LLM provider.
    Returns: (parsed_dict, tokens_used)
    
    CRITICAL: Includes a triple-provider failover (Primary -> Secondary -> Last Resort)
    """
    # 1. Try Primary Provider (from Bot Settings)
    try:
        api_key = await get_provider_api_key(provider, user_id)
        return await _call_provider(provider, model, system_prompt, user_prompt, api_key, response_schema, context)
    except Exception as e:
        log.warning(f"Primary provider {provider} failed: {str(e)}. Attempting first fallback...")
        
        # 2. Try Secondary Provider
        # Prefer Gemini first (most likely to have a working key), then Claude, then OpenRouter
        fallback_order = [LLMProvider.GEMINI, LLMProvider.CLAUDE, LLMProvider.OPENROUTER]
        if provider in fallback_order:
            fallback_order.remove(provider)
            
        for fallback_provider in fallback_order:
            try:
                # CRITICAL optimization: If we hit a quota limit (429) or billing error (400 balance)
                # don't bother retrying other models on the same provider if the logic does that.
                # Just move to the NEXT provider in the chain.
                fallback_key = await get_provider_api_key(fallback_provider, user_id)
                fallback_model = AVAILABLE_MODELS[fallback_provider][0]
                log.info(f"Retrying with fallback provider: {fallback_provider} ({fallback_model})")
                return await _call_provider(fallback_provider, fallback_model, system_prompt, user_prompt, fallback_key, response_schema, context)
            except Exception as fe:
                log.error(f"Fallback {fallback_provider} also failed: {str(fe)}")
                continue
        
        # If we got here, everything failed
        raise e

async def _call_provider(provider, model, system, user, key, schema, context):
    if provider == LLMProvider.CLAUDE:
        return await _call_claude(system, user, key, model, schema, context)
    elif provider == LLMProvider.GEMINI:
        return await _call_gemini(system, user, key, model, schema, context)
    elif provider == LLMProvider.OPENROUTER:
        return await _call_openrouter(system, user, key, model, schema, context)
    else:
        raise ValueError(f"Unknown provider: {provider}")

async def _call_openrouter(system, user, key, model, schema, context):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
    
    full_sys = f"{system}\n\nCONTEXT:\n{context}"
    
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": full_sys},
            {"role": "user", "content": user}
        ],
        response_format={"type": "json_object"}
    )
    
    content = resp.choices[0].message.content
    result = json.loads(content)
    tokens = resp.usage.total_tokens
    return result, tokens

# (Existing Claude/Gemini calls stay below, but I will fix Gemini name)


async def validate_provider(provider: str, user_id: str) -> None:
    """Perform a dummy check to verify the provider API key and model access."""
    try:
        api_key = await get_provider_api_key(provider, user_id)
        if provider == LLMProvider.GEMINI:
            genai.configure(api_key=api_key)
            # Use a fast, low-cost variant for health check
            # list_models is the authoritative way to check access
            await asyncio.to_thread(genai.list_models)
        elif provider == LLMProvider.CLAUDE:
            client = anthropic.Anthropic(api_key=api_key)
            # Minimal health check for Claude
            pass
        log.info(f"Connection to {provider} verified successfully.")
    except Exception as e:
        log.error(f"Provider {provider} validation failed: {str(e)}")
        raise ValueError(f"Could not connect to {provider}. Please check your credentials.")
async def _call_claude(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
    response_schema: type,
    context: str
) -> tuple[dict, int]:
    client = anthropic.Anthropic(api_key=api_key)
    
    schema = response_schema.model_json_schema()
    
    full_system = (
        f"{system_prompt}\n\n"
        f"CONTEXT INFORMATION:\n"
        f"{context}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Use the CONTEXT to answer. Be thorough.\n"
        f"2. If the context is missing specific details but is related to the topic, use your general knowledge to provide a helpful answer.\n"
        f"3. Only say you don't have information if the context is completely irrelevant to the user's question.\n"
        f"4. You MUST respond with valid JSON matching the schema below.\n"
        f"{json.dumps(schema, indent=2)}"
    )
    
    try:
        response = await asyncio.to_thread(
            client.messages.create,
            model=model,
            max_tokens=1024,
            system=full_system,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[{
                "name": "format_response",
                "description": "Format the chatbot response as structured JSON",
                "input_schema": schema
            }],
            tool_choice={"type": "tool", "name": "format_response"}
        )
        
        # Extract tool use result
        for block in response.content:
            if block.type == "tool_use":
                result = block.input
                tokens = (response.usage.input_tokens + 
                         response.usage.output_tokens)
                return result, tokens
        
        raise ValueError("Claude did not return tool use response")
    except Exception as e:
        log.error(f"Claude API call failed: {str(e)}")
        raise

def _normalize_gemini_name(name: str) -> str:
    """
    Remove 'models/' prefix to let the SDK handle routing.
    This resolves 404 issues seen in some regions using the v1beta endpoint.
    """
    name = name.lower().strip()
    if name.startswith("models/"):
        return name.replace("models/", "")
    return name

async def _call_gemini(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
    response_schema: type,
    context: str
) -> tuple[dict, int]:
    genai.configure(api_key=api_key)
    schema = response_schema.model_json_schema()
    tried_discovery = False
    
    full_system = (
        f"{system_prompt}\n\n"
        f"CONTEXT INFORMATION:\n"
        f"{context if context else 'No specific local context found.'}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. PRIMARY: Use the CONTEXT to answer.\n"
        f"2. FALLBACK: If context is sparse, use your general knowledge to be helpful.\n"
        f"3. FORMAT: Respond with valid JSON matching the schema below.\n"
        f"{json.dumps(schema, indent=2)}"
    )

    # Attempt with cleaned name
    model_path = _normalize_gemini_name(model)
    
    # Map deprecated model names to current equivalents
    async def _try_gen(m_path: str):
        # Standardize prefix for the SDK
        if not m_path.startswith("models/"):
            m_path = f"models/{m_path}"
        
        # We try to use the model, but we wrap it in a function we can retry
        gemini_model = genai.GenerativeModel(
            model_name=m_path,
            system_instruction=full_system,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        response = await asyncio.to_thread(gemini_model.generate_content, user_prompt)
        
        if not response or not response.text:
            raise ValueError("Gemini returned an empty response")
            
        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if len(lines) > 1 and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            log.error(f"Failed to parse Gemini response: {text}")
            raise ValueError("Gemini did not return valid JSON")
            
        tokens = (response.usage_metadata.prompt_token_count + 
                 response.usage_metadata.candidates_token_count)
        return result, tokens

    try:
        return await _try_gen(model_path)
    except Exception as e:
        err_msg = str(e).lower()
        log.warning(f"Gemini call failed for {model_path}: {err_msg}")
        
        # If we hit a quota limit, don't bother trying other models.
        # However, we only do this if we've already tried a couple of models.
        if ("quota" in err_msg or "429" in err_msg) and tried_discovery:
            log.info("Multiple Gemini models hit quota. Skipping provider.")
            raise e
        
        # AUTO-DISCOVERY: If 404, try calling for the list of models the key actually supports
        try:
            log.info("Attempting auto-discovery of available Gemini models...")
            models = await asyncio.to_thread(genai.list_models)
            available_names = [m.name for m in models if "generateContent" in m.supported_generation_methods]
            
            if available_names:
                # Sort models to prioritize 2.5 and 2.0+ (newest first)
                available_names.sort(reverse=True)
                
                for disco_model in available_names[:8]:
                    # Normalize discovered name for comparison (strip 'models/' prefix)
                    disco_normalized = _normalize_gemini_name(disco_model)
                    if disco_normalized != model_path:
                        try:
                            log.info(f"Auto-discovered and retrying with: {disco_normalized}")
                            return await _try_gen(disco_normalized)
                        except Exception as retry_err:
                            log.warning(f"Auto-discovered model {disco_normalized} also failed: {retry_err}")
                            continue
        except Exception as disco_err:
            log.error(f"Auto-discovery failed: {str(disco_err)}")

        # Fallback to hardcoded list if discovery failed (current models only)
        fallbacks = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"]
        for fb in fallbacks:
            fb_path = _normalize_gemini_name(fb)
            if fb_path != model_path:
                try:
                    log.info(f"Retrying with safety fallback: {fb_path}")
                    return await _try_gen(fb_path)
                except Exception:
                    continue
        raise
