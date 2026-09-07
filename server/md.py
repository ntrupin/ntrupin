import re
from functools import lru_cache
import nh3
from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from markdown.inlinepatterns import EscapeInlineProcessor, ESCAPE_RE
from markdown.util import AtomicString

MATH_PATTERNS = (
    re.compile(r'\\\[(?P<math>.+?)\\\]', re.S),   # \[ ... ] (display)
    re.compile(r'\\\((?P<math>.+?)\\\)', re.S),   # \( ... ) (inline)
    re.compile(r'\$\$(?P<math>.+?)\$\$', re.S),   # $$ ... $$ (display)
    re.compile(r'\$(?P<math>.+?)\$', re.S),       # $ ... $ (inline)
)

class KeepBackslashProcessor(EscapeInlineProcessor):
    _keep_chars = {'[', ']', '(', ')', '$'}

    def handleMatch(self, m, _):
        ch = m.group(1)
        if ch in self._keep_chars:
            return AtomicString("\\" + ch), m.start(0), m.end(0)
        else:
            return AtomicString(ch), m.start(0), m.end(0)

class MathJaxStashPreprocessor(Preprocessor):
    def run(self, lines):
        text = "\n".join(lines)
        for pat in MATH_PATTERNS:
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
    return sanitize(md.convert(text))

def contains_math(text: str | None) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in MATH_PATTERNS)


# Preserve Markdown structure, footnote anchors, and code-language classes.
# Scripts, event handlers, forms, and unsafe URLs are removed. Only a small
# set of layout styles is retained for the existing hand-formatted CV.
_HTML_CLEANER = nh3.Cleaner(
    tags=nh3.ALLOWED_TAGS | {"section", "aside"},
    attributes={
        **nh3.ALLOWED_ATTRIBUTES,
        "*": {"id", "title", "style"},
        "a": {"href", "title"},
        "code": {"class"},
        "img": {"src", "alt", "title", "width", "height"},
    },
    allowed_classes={
        "div": {"footnote", "ml-4"},
        "ul": {"cv-list"},
        "a": {"footnote-ref", "footnote-backref"},
    },
    attribute_filter=lambda tag, attr, value: (
        " ".join(name for name in value.split() if re.fullmatch(r"language-[\w+-]+", name))
        if tag == "code" and attr == "class" else value
    ),
    filter_style_properties={
        "text-align", "float", "margin-left", "margin-right",
        "margin-top", "margin-bottom", "padding-top", "padding-bottom",
    },
    url_schemes={"http", "https", "mailto"},
)

@lru_cache(maxsize=128)
def sanitize(html: str) -> str:
    """Also sanitize old stored HTML on read, without modifying the database."""
    return _HTML_CLEANER.clean(html)
