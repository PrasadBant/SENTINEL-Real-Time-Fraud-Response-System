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
