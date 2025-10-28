import sys
import os

# Add parent directory to path so we can import server
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app

# This is the entry point for Vercel
# It imports the Flask app from server.py
