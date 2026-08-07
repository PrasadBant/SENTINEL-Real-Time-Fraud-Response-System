import os
import random
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
import joblib

def generate_synthetic_data(n_samples=10000):
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
        amount = np.clip(random.gauss(0.2, 0.15), 0, 1)
        hour = random.uniform(0.0, 1.0)
        is_new = 1.0 if random.random() < 0.3 else 0.0
        velocity = np.clip(random.gauss(0.2, 0.2), 0, 1)
        chain = np.clip(random.gauss(0.1, 0.2), 0, 1)
        call = 1.0 if random.random() < 0.1 else 0.0
        
        is_fraud = False
        
        # Rule 1: High amounts are risky
        if amount > 0.8 and random.random() < 0.7:
            is_fraud = True
            
        # Rule 2: Active call + new receiver is very risky (Social Engineering)
        if call == 1.0 and is_new == 1.0 and random.random() < 0.8:
            is_fraud = True
            
        # Rule 3: Non-linear relationship - Small amounts are usually safe, 
        # UNLESS it's late night AND it's a new receiver
        is_late_night = hour > 0.9 or hour < 0.2
        if amount < 0.3 and is_late_night and is_new == 1.0:
            is_fraud = True
            
        # Rule 4: High velocity + chain depth > 0 (Mule behavior)
        if velocity > 0.7 and chain > 0.2:
            is_fraud = True
            
        if is_fraud:
            # Overwrite some features to make them look more fraudulent
            if not is_late_night and random.random() < 0.3:
                hour = random.choice([random.uniform(0, 0.2), random.uniform(0.9, 1.0)])
            if amount < 0.3 and random.random() < 0.3:
                amount = np.clip(random.gauss(0.8, 0.2), 0, 1)

        # Add slight noise to labels to prevent perfect overfitting
        final_label = 1 if is_fraud else 0
        if random.random() < 0.03:
            final_label = 1 - final_label
            
        labels.append(final_label)
        data.append([amount, hour, is_new, velocity, chain, call])
        
    df = pd.DataFrame(data, columns=["amount", "hour", "is_new_receiver", "velocity", "chain_depth", "call_flag"])
    return df, np.array(labels)

if __name__ == "__main__":
    X, y = generate_synthetic_data(15000)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training XGBoost Classifier...")
    model = XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
        eval_metric='logloss'
    )
    model.fit(X_train, y_train)
    
    score = model.score(X_test, y_test)
    print(f"Model Accuracy on Test Set: {score*100:.2f}%")
    
    # Save the model
    os.makedirs(os.path.join(os.path.dirname(__file__), "../app/data"), exist_ok=True)
    model_path = os.path.join(os.path.dirname(__file__), "../app/data/xgb_model.joblib")
    joblib.dump(model, model_path)
    print(f"Model saved successfully to {model_path}")
