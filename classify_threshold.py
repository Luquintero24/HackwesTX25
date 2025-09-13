# classify.py
def classify_value(value, th):
    """
    value: numeric
    th: Threshold row (SQLAlchemy object)
    returns: str ('LOW','MEDIUM','HIGH','OK')
    """
    # Only check if thresholds exist
    if th.alarm_low is not None and value <= th.alarm_low:
        return "HIGH"
    if th.warn_low is not None and value <= th.warn_low:
        return "MEDIUM"
    if th.alarm_high is not None and value >= th.alarm_high:
        return "HIGH"
    if th.warn_high is not None and value >= th.warn_high:
        return "MEDIUM"
    return "OK"
