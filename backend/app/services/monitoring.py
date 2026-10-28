"""Read-only metrics with allowlisted fields and server-selected infrastructure."""

import math


def number(value, default=0):
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ):
        return max(0, value)
    return default


def vm_metrics(status):
    return {
        "cpu_percent": round(min(1, number(status.get("cpu"))) * 100, 1),
        "cpu_count": int(number(status.get("cpus"))),
        "memory_used": int(number(status.get("mem"))),
        "memory_total": int(number(status.get("maxmem"))),
        "uptime_seconds": int(number(status.get("uptime"))),
        "net_in": int(number(status.get("netin"))),
        "net_out": int(number(status.get("netout"))),
    }
