# NOTE: this produces app/data/rf_model.joblib as an alternative to
# train_xgb_model.py, but nothing in app/services/ml_risk_engine.py loads
# it — XGBoost is the model actually wired into the scoring pipeline.
# Kept as a reference/experiment; run train_xgb_model.py for the model
# that's actually used at runtime.

import os
import random
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import joblib

def generate_synthetic_data(n_samples=5000):
    """
    Generate synthetic data for transaction fraud detection.
    Features: amount (0-1), hour (0-1), is_new_receiver (0,1), 
              velocity (0-1), chain_depth (0-1), call_flag (0,1)
    """
    print(f"Generating {n_samples} synthetic transaction samples...")
    data = []
    labels = []
    
    for _ in range(n_samples):
        # Base distributions
        is_fraud = random.random() < 0.15  # 15% fraud rate
        
        if is_fraud:
            # Fraudulent patterns (e.g. high amounts, night time, new receivers, fast velocity)
            amount = np.clip(random.gauss(0.8, 0.2), 0, 1)
            hour = random.choice([random.uniform(0, 0.2), random.uniform(0.9, 1.0)]) # late night
            is_new = 1.0 if random.random() < 0.8 else 0.0
            velocity = np.clip(random.gauss(0.7, 0.2), 0, 1)
            chain = np.clip(random.gauss(0.4, 0.3), 0, 1)
            call = 1.0 if random.random() < 0.6 else 0.0
        else:
            # Normal patterns
            amount = np.clip(random.gauss(0.2, 0.15), 0, 1)
            hour = random.uniform(0.3, 0.8) # daytime
            is_new = 1.0 if random.random() < 0.2 else 0.0
            velocity = np.clip(random.gauss(0.2, 0.1), 0, 1)
            chain = 0.0
            call = 1.0 if random.random() < 0.05 else 0.0
            
        # Add some noise to prevent overfitting
        if random.random() < 0.05:
            labels.append(1 if not is_fraud else 0)
        else:
            labels.append(1 if is_fraud else 0)
            
        data.append([amount, hour, is_new, velocity, chain, call])
        
    df = pd.DataFrame(data, columns=["amount", "hour", "is_new_receiver", "velocity", "chain_depth", "call_flag"])
    return df, np.array(labels)

if __name__ == "__main__":
    X, y = generate_synthetic_data(10000)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest Classifier...")
    model = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    model.fit(X_train, y_train)
    
    score = model.score(X_test, y_test)
    print(f"Model Accuracy on Test Set: {score*100:.2f}%")
    
    # Save the model
    os.makedirs(os.path.join(os.path.dirname(__file__), "../app/data"), exist_ok=True)
    model_path = os.path.join(os.path.dirname(__file__), "../app/data/rf_model.joblib")
    joblib.dump(model, model_path)
    print(f"Model saved successfully to {model_path}")
