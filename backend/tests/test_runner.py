import sys
import os
from datetime import datetime, timezone

# Add parent directory to path to allow imports when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from app.core.data_store import data_store
    from app.services.orchestrator import run_pipeline
    
    print("All modules imported successfully.")
    
    tx = {
        "tx_id": "TX-1001",
        "sender_account": "ACC-1001",
        "receiver_account": "ACC-1002",
        "amount": 150.50,
        "channel": "WEB",
        "timestamp": "2023-01-01T00:00:00Z"
    }
    
    result = run_pipeline(tx, data_store)
    
    print(f"Created Test Transaction: {result['transaction']['tx_id']}")
    print("Test passed.")
    
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Test failed with error: {e}")
    sys.exit(1)
