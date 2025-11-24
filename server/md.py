import re
from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.inlinepatterns import EscapeInlineProcessor, ESCAPE_RE
from markdown.util import AtomicString

class KeepBackslashProcessor(EscapeInlineProcessor):
    _keep_chars = {'[', ']', '(', ')', '$'}

    def handleMatch(self, m, _):
        ch = m.group(1)
        if ch in self._keep_chars:
            return AtomicString("\\" + ch), m.start(0), m.end(0)
        else:
            return AtomicString(ch), m.start(0), m.end(0)

class MathJaxStashPreprocessor(Preprocessor):
    _patterns = [
        re.compile(r'\\\[(?P<math>.+?)\\\]', re.S),   # \[ ... ] (display)
        re.compile(r'\\\((?P<math>.+?)\\\)', re.S),   # \( ... ) (inline)
        re.compile(r'\$\$(?P<math>.+?)\$\$', re.S),   # $$ ... $$ (display)
        re.compile(r'\$(?P<math>.+?)\$', re.S),       # $ ... $ (inline)
    ]

    def run(self, lines):
        text = "\n".join(lines)
        for pat in self._patterns:
            def _stash(m):
                return self.md.htmlStash.store(m.group(0))
            text = pat.sub(_stash, text)
        return text.split("\n")

class MathSafeExtension(Extension):
    def extendMarkdown(self, md: Markdown):
        md.preprocessors.register(MathJaxStashPreprocessor(md), "mathjax-stash", 25)
        md.inlinePatterns.deregister("escape")
        md.inlinePatterns.register(KeepBackslashProcessor(ESCAPE_RE, md), "escape", 180)

def render(text: str) -> str:
    md = Markdown(
        extensions=[
            "footnotes",
            "fenced_code",
            MathSafeExtension()
        ],
        extension_configs={
            "footnotes": {
                "UNIQUE_IDS": True,
                "BACKLINK_TEXT": "",
            }
        }
    )
    return md.convert(text)
