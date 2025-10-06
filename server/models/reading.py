from dataclasses import dataclass
from datetime import datetime

@dataclass
class Reading:
    id: int
    created_at: datetime
    link: str
    text: str

    @classmethod
    def from_dict(cls, data: dict) -> "Reading":
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            link=data["link"],
            text=data["text"]
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "link": self.link,
            "text": self.text
        }
