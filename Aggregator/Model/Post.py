from dataclasses import dataclass
from typing import Optional

@dataclass
class Post:
    title: str
    text: str
    date: str
    source: str
    url: str
    image: str
    image_path: str
    links: dict
    id: Optional[int] = None
    is_news: Optional[int] = None
    text_processed: str = ''
    institute: Optional[list[str]] = None
    faculty: Optional[list[str]] = None
    department: Optional[list[str]] = None
