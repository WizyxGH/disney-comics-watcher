"""Tracks whether each provider still returns anything, across runs.

Scrapers swallow their own errors and return an empty list: one hourly run
finding nothing is normal noise (Panini IT and ES come back empty about one
run in three), but a source blocked for good (Kathimerini answering 403 to
GitHub's runners) used to look exactly the same, and only a reading of the
logs revealed it. The counters live in state.json under one key, so they
survive between the CI runs like the rest of the state.
"""

HEALTH_KEY = "_health"


def has_history(state: dict, key_prefix: str) -> bool:
    """A provider that never returned anything is a stub, not a broken source."""
    return any(k.startswith(key_prefix) for k in state if k != HEALTH_KEY)


def update_provider_health(state: dict, name: str, key_prefix: str, count: int,
                           alert_after: int) -> str | None:
    """Records this run's result for a provider; returns the admin message to
    send when it has just gone silent for `alert_after` runs, or just recovered."""
    if not has_history(state, key_prefix):
        return None
    health = state.setdefault(HEALTH_KEY, {})
    entry = health.get(name, {"empty_runs": 0, "alerted": False})

    if count:
        recovered = entry["alerted"]
        silent_for = entry["empty_runs"]
        health.pop(name, None)
        if recovered:
            return f"✅ {name} is back: {count} item(s) after {silent_for} empty run(s)."
        return None

    entry["empty_runs"] += 1
    health[name] = entry
    if entry["empty_runs"] == alert_after and not entry["alerted"]:
        entry["alerted"] = True
        return (f"⚠️ {name} has returned nothing for {alert_after} runs in a row. "
                f"The site is probably blocking the runner or has changed its layout: "
                f"see the '[{name}]' lines of the last watcher run.")
    return None
