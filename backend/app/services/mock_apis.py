def mock_bank_freeze(account_id: str, amount: float) -> dict:
    return {"status": "SUCCESS", "message": f"Account {account_id} frozen for {amount}"}

def mock_telecom_flag(account_id: str) -> dict:
    return {"status": "SUCCESS", "message": f"Account {account_id} flagged"}

def mock_police_alert(case_id: str, evidence: dict) -> dict:
    return {"status": "SUCCESS", "message": f"Case {case_id} alerted to police"}

def mock_monitor_account(account_id: str) -> dict:
    return {"status": "SUCCESS", "message": f"Account {account_id} added to monitoring"}

def mock_close_case(case_id: str, resolution: str) -> dict:
    return {"status": "SUCCESS", "message": f"Case {case_id} closed as {resolution}"}
