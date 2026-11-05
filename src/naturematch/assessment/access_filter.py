"""Step 1: essential access requirements. Runs BEFORE any preference ranking."""


def passes(place: dict, required: dict) -> tuple[bool, list[str]]:
    reasons = [f"missing {k}" for k, need in required.items() if need and not place.get(k)]
    return (not reasons, reasons)
