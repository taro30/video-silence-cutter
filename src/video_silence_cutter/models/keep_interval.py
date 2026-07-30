from dataclasses import dataclass

@dataclass(frozen=True)
class KeepInterval:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)
