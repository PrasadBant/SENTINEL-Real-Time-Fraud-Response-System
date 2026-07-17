import torch
import torch.nn as nn
import os

class FraudNet(nn.Module):
    """
    A simple Feed-Forward Neural Network for Fraud Detection.
    Takes numerical and categorical (one-hot/binary) features and 
    outputs a fraud probability score (0 to 1).
    """
    def __init__(self, input_dim=10):
        super(FraudNet, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, 1),
            nn.Sigmoid()
        )
        
        # For the hackathon, we manually set some weights so the model
        # isn't completely random and actually flags risky features.
        # This simulates a pre-trained model.
        with torch.no_grad():
            # First layer: positive weights for risky flags
            nn.init.constant_(self.network[0].weight, 0.1)
            # Give higher weight to some features (e.g. cross_border, crypto)
            self.network[0].weight[0, 1] = 0.8  # cross_border
            self.network[0].weight[0, 4] = 0.8  # crypto
            self.network[0].weight[0, 5] = 0.7  # remote_access
            
            # Second layer
            nn.init.constant_(self.network[2].weight, 0.5)
            
            # Output layer
            nn.init.constant_(self.network[4].weight, 1.0)
            nn.init.constant_(self.network[4].bias, -2.0) # Bias towards 0

    def forward(self, x):
        return self.network(x)


# Instantiate a global instance (simulate loading a saved model)
model = FraudNet(input_dim=10)
model.eval()

def predict(features: dict) -> float:
    """
    Takes a dictionary of features, converts to tensor, and runs inference.
    Returns a score from 0 to 100.
    """
    # Define the 10 features we extract
    # 0: amount_scaled (amount / 100000)
    # 1: is_cross_border
    # 2: device_changed
    # 3: bulk_transfer_flag
    # 4: is_crypto_related
    # 5: is_remote_access_active
    # 6: is_scripted
    # 7: new_payee_added
    # 8: velocity_flag
    # 9: hop_number
    
    amount_scaled = min(float(features.get("amount", 0)) / 100000.0, 10.0)
    
    input_tensor = torch.tensor([[
        amount_scaled,
        1.0 if features.get("is_cross_border") else 0.0,
        1.0 if (features.get("device_changed") or features.get("location_changed")) else 0.0,
        1.0 if features.get("bulk_transfer_flag") else 0.0,
        1.0 if features.get("is_crypto_related") else 0.0,
        1.0 if features.get("is_remote_access_active") else 0.0,
        1.0 if features.get("is_scripted") else 0.0,
        1.0 if (features.get("new_payee_added") or features.get("is_first_time_payee")) else 0.0,
        1.0 if features.get("velocity_flag") else 0.0,
        float(features.get("hop_number", 0))
    ]], dtype=torch.float32)

    with torch.no_grad():
        output = model(input_tensor)
        score = output.item() * 100.0
        
    return score
