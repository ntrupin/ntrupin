from markdown import Markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import EscapeInlineProcessor, ESCAPE_RE
from markdown.util import AtomicString

class KeepBackslashProcessor(EscapeInlineProcessor):
    def handleMatch(self, m, _):
        return AtomicString(m.group(0)), m.start(0), m.end(0)

class KeepBackslashExtension(Extension):
    def extendMarkdown(self, md: Markdown):
        md.inlinePatterns.deregister("escape")
        md.inlinePatterns.register(KeepBackslashProcessor(ESCAPE_RE, md), "escape", 180)

def render(text: str) -> str:
    md = Markdown(
        extensions=[
            "footnotes", 
            KeepBackslashExtension()
        ],
        extension_configs={
            "footnotes": {
                "UNIQUE_IDS": True,
                "BACKLINK_TEXT": "",
            }
        }
    )
    return md.convert(text)
