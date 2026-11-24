from dataclasses import dataclass
from typing import Optional


@dataclass
class Job:
    title: str
    company: str
    location: str
    country: str
    url: str
    description: str
    source: str

    original_url: Optional[str] = None
    description_complete: bool = False