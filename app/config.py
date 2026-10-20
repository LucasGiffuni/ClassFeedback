import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./classfeedback.db"
    session_ttl_seconds: int = 86400

    def __post_init__(self) -> None:
        if self.session_ttl_seconds <= 0:
            raise ValueError("SESSION_TTL_SECONDS debe ser positivo")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("DATABASE_URL", "sqlite:///./classfeedback.db"),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "86400")),
        )
