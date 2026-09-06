data_store = {
    "transactions": {},
    "cases": {},
    "graphs": {},
    "actions": []
}
# "accounts" and "velocity_cache" used to live here; both moved to Redis
# in Phase 1 (see app/services/orchestrator.py's record_velocity/
# get_account/save_account) so this state is correct across multiple API
# replicas instead of being per-process.
