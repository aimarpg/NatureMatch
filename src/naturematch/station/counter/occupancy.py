class Occupancy:
    """Estimated occupancy from a known initial count. Never negative."""

    def __init__(self, initial: int = 0):
        self.count = initial

    def apply(self, direction: str) -> int:
        if direction == "in":
            self.count += 1
        elif direction == "out":
            self.count = max(0, self.count - 1)
        return self.count
