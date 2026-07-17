class CaseStatus:
    NEW = "NEW"
    HIGH_RISK = "HIGH_RISK"
    ACTIONED = "ACTIONED"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"
    CLOSED_FP = "CLOSED_FP"

class AccountStatus:
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    WITHDRAWN = "WITHDRAWN"

class ActionTypes:
    FREEZE = "FREEZE"
    FLAG = "FLAG"
    ALERT = "ALERT"
