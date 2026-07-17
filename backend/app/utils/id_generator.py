class IDGenerator:
    _tx_counter = 0
    _case_counter = 0
    _account_counter = 0
    _action_counter = 0
    
    @classmethod
    def generate_tx_id(cls) -> str:
        cls._tx_counter += 1
        return f"TX-{cls._tx_counter:03d}"
        
    @classmethod
    def generate_case_id(cls) -> str:
        cls._case_counter += 1
        return f"CASE-{cls._case_counter:03d}"
        
    @classmethod
    def generate_account_id(cls) -> str:
        cls._account_counter += 1
        return f"ACC-{cls._account_counter:04d}"
        
    @classmethod
    def generate_action_id(cls) -> str:
        cls._action_counter += 1
        return f"ACT-{cls._action_counter:03d}"
