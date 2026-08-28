from enum import StrEnum

from pydantic import BaseModel, Field


class BuiltinMode(StrEnum):
    SOLO = "solo"
    PAIR = "pair"
    SWARM = "swarm"
    REVIEW = "review"


class ValidationPreset(StrEnum):
    LIGHT = "light"
    STANDARD = "standard"
    STRICT = "strict"


class ValidationCadence(StrEnum):
    FINAL = "final"
    CHECKPOINT = "checkpoint"
    CONTINUOUS = "continuous"


class ValidationAuthority(StrEnum):
    ADVISORY = "advisory"
    BLOCKING = "blocking"


class ValidationPolicy(BaseModel):
    cadence: ValidationCadence = ValidationCadence.CHECKPOINT
    authority: ValidationAuthority = ValidationAuthority.BLOCKING
    max_rounds: int = Field(default=3, ge=1, le=20)
    independent_context: bool = True


class ModeConfiguration(BaseModel):
    mode: BuiltinMode = BuiltinMode.PAIR
    validation: ValidationPreset = ValidationPreset.STANDARD
    policy: ValidationPolicy = Field(default_factory=ValidationPolicy)
