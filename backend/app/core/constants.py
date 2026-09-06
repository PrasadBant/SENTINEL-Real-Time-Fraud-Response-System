class CaseStatus:
    NEW = "NEW"
    HIGH_RISK = "HIGH_RISK"
    ACTIONED = "ACTIONED"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"
    CLOSED_FP = "CLOSED_FP"

class AccountStatus:
    # NOTE: lowercase is intentional — this matches the values actually
    # written/read throughout the engines (graph_engine, recovery_engine,
    # withdrawal_simulator) and already persisted in sentinel.db. Do not
    # change the case here without a data migration.
    ACTIVE = "active"
    FROZEN = "frozen"
    WITHDRAWN = "withdrawn"

class ActionTypes:
    FREEZE = "FREEZE"
    FLAG = "FLAG"
    ALERT = "ALERT"
    MONITOR = "MONITOR"
    CLOSE = "CLOSE"
    CLOSE_FP = "CLOSE_FP"

class ActionStatus:
    ACK = "ACK"
    NACK = "NACK"


# Single-tenant placeholder (see app/core/db_models.py's tenant_id columns).
# There is exactly one tenant today, but every domain table carries this
# column from day one — retrofitting tenant_id onto live tables later is
# far more expensive than shipping it unused now. Real multi-tenancy
# (per-tenant provisioning, auth scoping, tenant-scoped queries) is
# Phase 2+ work; for now every row is just stamped with this fixed value.
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"
