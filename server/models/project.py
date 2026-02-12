from dataclasses import dataclass
from datetime import date, datetime

@dataclass
class Project:
    id: int
    created_at: datetime
    user_id: int
    published_at: datetime
    updated_at: datetime
    started_on: date | None
    ended_on: date | None
    title: str
    summary: str | None
    content: str | None
    html: str | None
    canonical_url: str | None
    status: str | None
    stack: str | None
    project_url: str | None
    repo_url: str | None
    public: bool

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            user_id=data["user_id"],
            published_at=datetime.fromisoformat(data["published_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            started_on=date.fromisoformat(data["started_on"]) if data.get("started_on") else None,
            ended_on=date.fromisoformat(data["ended_on"]) if data.get("ended_on") else None,
            title=data["title"],
            summary=data.get("summary"),
            content=data.get("content"),
            html=data.get("html"),
            canonical_url=data.get("canonical_url"),
            status=data.get("status"),
            stack=data.get("stack"),
            project_url=data.get("project_url"),
            repo_url=data.get("repo_url"),
            public=data["public"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
            "published_at": self.published_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_on": self.started_on.isoformat() if self.started_on else None,
            "ended_on": self.ended_on.isoformat() if self.ended_on else None,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "html": self.html,
            "canonical_url": self.canonical_url,
            "status": self.status,
            "stack": self.stack,
            "project_url": self.project_url,
            "repo_url": self.repo_url,
            "public": self.public,
        }
