from dataclasses import dataclass
from datetime import datetime

@dataclass
class Writing:
    id: int
    created_at: datetime
    user_id: int
    published_at: datetime
    updated_at: datetime
    title: str
    content: str | None
    canonical_url: str | None
    public: bool

    @classmethod
    def from_dict(cls, data: dict) -> "Writing":
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            user_id=data["user_id"],
            published_at=datetime.fromisoformat(data["published_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            title=data["title"],
            content=data.get("content"),
            canonical_url=data.get("canonical_url"),
            public=data["public"]
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
            "published_at": self.published_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "title": self.title,
            "content": self.content,
            "canonical_url": self.canonical_url,
            "public": self.public
        }
