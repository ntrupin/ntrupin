from dataclasses import asdict, dataclass, field
from datetime import datetime

from flask import request
from server.i18n import translate, locale

BASE = "https://ntrupin.com"

@dataclass
class Metadata:
    base: str = BASE
    title: str = "Noah Trupin"
    description: str = "Noah Trupin's personal website."
    openGraph: dict = field(default_factory=lambda: { # type: ignore
        "title": "Noah Trupin",
        "description": "Noah Trupin's personal website.",
        "url": BASE + request.path,
        "siteName": "Noah Trupin",
        "locale": "en_US",
        "type": "website"
    })
    robots: dict = field(default_factory=lambda: { # type: ignore
        "index": True,
        "follow": True
    })
    googlebot: dict = field(default_factory=lambda: { # type: ignore
        "index": True,
        "follow": True,
        "max-video-preview": -1,
        "max-image-preview": "large",
        "max-snippet": -1
    })
    links: dict = field(default_factory=lambda: { # type: ignore
        "/": { "name": "Home" },
        "/cv": { "name": "CV" },
        # "/reading": { "name": "Reading" },
        # "/projects": { "name": "Projects" },
        "/writing": { "name": "Writing" },
        "https://linkedin.com/in/ntrupin/": {
            "name": "LinkedIn",
            "external": True
        },
    })
    timestamp: str | None = None

    def serialize(self) -> dict:
        botify = lambda d: ", ".join(
            f"{k}" if v is True else f"no{k}" if v is False
            else f"{k}:{v}" for k, v in d.items()
        )

        data = asdict(self)
        data["title"] = translate(self.title)
        data["description"] = translate(self.description)
        data["openGraph"]["locale"] = "ko_KR" if locale() == "ko" else "en_US"
        data["openGraph"]["title"] = data["title"]
        data["openGraph"]["description"] = data["description"]
        data["robots"] = botify(self.robots)
        data["googlebot"] = botify(self.googlebot)
        data["timestamp"] = datetime.utcnow().isoformat()
        return data
