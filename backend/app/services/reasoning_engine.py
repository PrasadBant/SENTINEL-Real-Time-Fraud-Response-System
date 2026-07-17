MAX_REASON_LENGTH = 120

def truncate_reason(text: str, max_len: int = MAX_REASON_LENGTH) -> str:
    """Safely truncate reason string to max length without breaking UI."""
    if not text:
        return ""
        
    if len(text) <= max_len:
        return text
        
    truncated = text[:max_len - 3]
    last_plus_idx = truncated.rfind(" + ")
    
    if last_plus_idx != -1:
        clean_cut = truncated[:last_plus_idx]
        if clean_cut.strip():
            return clean_cut.rstrip() + "..."
            
    return truncated.rstrip() + "..."

def generate_reasoning(risk_factors: list) -> dict:
    """
    Convert risk_factors into a human-readable explanation string.
    """
    if not risk_factors:
        return {
            "short_reason": "Insufficient data",
            "full_reason": "Insufficient data for reasoning"
        }

    # Human-readable mapping for known factors
    factor_mapping = {
        "new_receiver": "New receiver",
        "amount_deviation": "High transaction amount",
        "time_anomaly": "Off-hours activity",
        "velocity_spike": "Rapid transaction pattern",
        "call_flag": "Suspicious telecom activity",
        "cross_border_risk": "High-risk cross-border activity",
        "device_anomaly": "Device or location mismatch",
        "bulk_transfer": "Unusual bulk transfer",
        "crypto_risk": "Suspected crypto drain",
        "remote_access": "Active remote access detected",
        "scripted_behavior": "Automated behavior pattern",
        "first_time_payee": "First-time payee alert"
    }

    # Filter and sort
    valid_factors = [f for f in risk_factors if f.get("contribution", 0) > 10]
    valid_factors.sort(key=lambda x: x.get("contribution", 0), reverse=True)

    if not valid_factors:
        return {
            "short_reason": "Low risk pattern",
            "full_reason": "Low-risk pattern detected"
        }

    unique_reasons = []
    seen_names = set()
    
    for factor in valid_factors:
        raw_name = factor.get("name", "")
        # Fallback to Title Case if not in mapping
        readable_name = factor_mapping.get(raw_name, raw_name.replace("_", " ").title())
        contribution = round(factor.get("contribution", 0))
        
        reason_str = readable_name
        
        if readable_name not in seen_names:
            seen_names.add(readable_name)
            unique_reasons.append(reason_str)

    # Take top 4 factors max for full, top 2 for short
    full_factors = unique_reasons[:4]
    short_factors = unique_reasons[:2]

    full_reason_str = " + ".join(full_factors)

    return {
        "short_reason": " + ".join(short_factors),
        "full_reason": truncate_reason(full_reason_str)
    }
