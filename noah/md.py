from markdown import markdown

def render(md: str) -> str:
    return markdown(md, extensions=["fenced_code", "tables", "nl2br", "toc"])
