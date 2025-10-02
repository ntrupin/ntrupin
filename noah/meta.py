from dataclasses import asdict, dataclass, field
from datetime import datetime

BASE = "https://ntrupin.com/"

@dataclass
class Metadata:
    base: str = BASE
    title: str = "Noah Trupin"
    description: str = "Noah Trupin's personal website."
    openGraph: dict = field(default_factory=lambda: { # type: ignore
        "title": "Noah Trupin",
        "description": "Noah Trupin's personal website.",
        "url": BASE,
        "siteName": "Noah Trupin",
        "locale": "en_US",
        "type": "website"
    })
    robots: dict = field(default_factory=lambda: { # type: ignore
        "index": True,
        "follow": True
    })
    googleBot: dict = field(default_factory=lambda: { # type: ignore
        "index": True,
        "follow": True,
        "max-video-preview": -1,
        "max-image-preview": "large",
        "max-snippet": -1
    })
    links: dict = field(default_factory=lambda: { # type: ignore
        "/": { "name": "Home" },
        "/cv": { "name": "CV" },
        "https://linkedin.com/in/ntrupin/": {
            "name": "LinkedIn",
            "external": True
        },
    })
    timestamp: str | None = None

    def serialize(self) -> dict:
        botify = lambda d: ", ".join(
            f"{k}" if v is True else "no{k}" if v is False 
            else f"{k}:{v}" for k, v in d.items()
        )

        data = asdict(self)
        data["robots"] = botify(self.robots)
        data["googleBot"] = botify(self.googleBot)
        data["timestamp"] = datetime.utcnow().isoformat()
        return data
