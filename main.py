"""
Railway entrypoint for running the API server.
"""

from api_server import create_app
from system_initialization import initialize_system

pipeline = initialize_system()
app = create_app(pipeline)

