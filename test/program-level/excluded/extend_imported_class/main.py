from dataclasses import dataclass
from base import Base

@dataclass
class Derived(Base):  # Base is imported, not locally declared — should be rejected
    y: int
