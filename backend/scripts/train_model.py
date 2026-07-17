import os
import json
import random
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

# Paths
DATA_DIR = "backend/data"
MODEL_DIR = "backend/models"
DATA_FILE = os.path.join(DATA_DIR, "transactions.json")
MODEL_FILE = os.path.join(MODEL_DIR, "fraud_model.pkl")

# Feature names tracker
feature_names = [
    "amount",
    "hour",
    "is_new_receiver",
    "velocity",
    "chain_depth",
    "call_flag"
]

def normalize(tx):
    """Normalize features for better model stability."""
    return [
        min(tx["amount"] / 100000, 1.0),
        tx["hour"] / 23.0,
        tx["is_new_receiver"],
        min(tx["velocity"] / 10, 1.0),
        min(tx["chain_depth"] / 5, 1.0),
        tx["call_flag"]
    ]

def generate_synthetic_data(n=2000):
    """Generate synthetic fraud data for training."""
    data = []
    for _ in range(n):
        amount = random.uniform(100, 500000)
        hour = random.randint(0, 23)
        is_new_receiver = 1 if random.random() < 0.3 else 0
        velocity = random.randint(1, 10)
        chain_depth = random.randint(0, 5)
        call_flag = 1 if random.random() < 0.1 else 0
        
        # Heuristic label for training
        label = 0
        if amount > 100000 and is_new_receiver == 1: label = 1
        if velocity > 5 and call_flag == 1: label = 1
        if (hour >= 22 or hour < 6) and amount > 50000: label = 1
        if chain_depth > 2: label = 1
        
        # Add noise
        if random.random() < 0.05:
            label = 1 - label
            
        data.append({
            "amount": amount,
            "hour": hour,
            "is_new_receiver": is_new_receiver,
            "velocity": velocity,
            "chain_depth": chain_depth,
            "call_flag": call_flag,
            "label": label
        })
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Generated {n} synthetic samples in {DATA_FILE}")

def train_model():
    """Load data, normalize, train RandomForest, and save with metadata."""
    if not os.path.exists(DATA_FILE):
        generate_synthetic_data()
        
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
        
    X = [normalize(tx) for tx in data]
    y = [tx["label"] for tx in data]
    
    X = np.array(X)
    y = np.array(y)
    
    print(f"Training on {len(X)} samples with {len(feature_names)} features...")
    model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    model.fit(X, y)
    
    os.makedirs(MODEL_DIR, exist_ok=True)
    # Save both model and feature names for alignment
    joblib.dump((model, feature_names), MODEL_FILE)
    print(f"Model and feature metadata saved to {MODEL_FILE}")

if __name__ == "__main__":
    train_model()
