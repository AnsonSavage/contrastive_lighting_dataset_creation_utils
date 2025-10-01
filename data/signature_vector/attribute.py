from abc import ABC, abstractmethod
import random
from enum import Enum
from typing import Dict, Optional, Sequence, TypeVar, Type

E = TypeVar("E", bound="EnumAttribute")

class Attribute(ABC):
    @abstractmethod
    def sample_value(cls, rng: random.Random):
        pass

class InvariantAttribute(Attribute):
    pass

class VariantAttribute(Attribute):
    pass

class EnumAttribute(Enum):
    """Mixin base for Enums that can sample a member.

    Usage:
        class MyEnum(SampleableEnum):
            A = auto()
            B = auto()
            C = auto()

        rng = random.Random()
        # Uniform sampling
        value = MyEnum.sample(rng)

        # Importance sampling (specify weights; unspecified members default to 1.0)
        value = MyEnum.sample(rng, weights={MyEnum.A: 5.0, MyEnum.C: 0.2})

    The weights mapping can be partial; any member not present defaults to weight 1.0.
    Weights must be non‑negative and not all zero.
    """

    @classmethod
    def _weighted_sample(cls: Type[E], rng: random.Random, weights: Optional[Dict[E, float]] = None) -> E:
        members: Sequence[E] = list(cls)  # type: ignore
        if not members:
            raise ValueError(f"Enum {cls.__name__} has no members to sample.")

        if weights is None or len(weights) == 0:
            return rng.choice(members)

        # Build aligned weights list, defaulting missing members to 1.0
        aligned_weights: list[float] = []
        for m in members:
            w = float(weights.get(m, 1.0))
            if w < 0:
                raise ValueError(f"Weight for {m} must be non-negative, got {w}.")
            aligned_weights.append(w)

        if all(w == 0 for w in aligned_weights):
            raise ValueError("All sampling weights are zero.")

        # Use built-in weighted sampling (k=1) and return the single element
        return rng.choices(members, weights=aligned_weights, k=1)[0]

    def sample_value(cls, rng: random.Random):
        return cls._weighted_sample(rng)