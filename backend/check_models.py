import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load env from root folder
load_dotenv("../.env")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # Try alternate name
    api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("ERROR: API Key not found in root .env")
    exit(1)

genai.configure(api_key=api_key)

print(f"Checking models for key: {api_key[:5]}...{api_key[-5:]}")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"AVAILABLE: {m.name}")
except Exception as e:
    print(f"FAILED to list models: {str(e)}")
