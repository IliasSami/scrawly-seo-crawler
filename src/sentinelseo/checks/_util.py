import re
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

_CHAR_W = {  # width in px per character (title scale)
    'i': 4, 'l': 4, 'j': 4, '.': 4, ',': 4, ':': 4, ';': 4, "'": 3, '!': 4,
    'f': 5, 't': 5, 'r': 6, ' ': 5, 'I': 5,
    'a': 9, 'b': 10, 'c': 8, 'd': 10, 'e': 9, 'g': 10, 'h': 10, 'k': 9,
    'm': 15, 'n': 10, 'o': 10, 'p': 10, 'q': 10, 's': 8, 'u': 10, 'v': 9,
    'w': 13, 'x': 9, 'y': 9, 'z': 8,
    'A': 12, 'B': 12, 'C': 13, 'D': 13, 'E': 12, 'F': 11, 'G': 14, 'H': 13,
    'J': 9, 'K': 12, 'L': 10, 'M': 15, 'N': 13, 'O': 14, 'P': 12, 'Q': 14,
    'R': 13, 'S': 12, 'T': 11, 'U': 13, 'V': 12, 'W': 17, 'X': 12, 'Y': 12,
    'Z': 11, '0': 10, '1': 10, '2': 10, '3': 10, '4': 10, '5': 10, '6': 10,
    '7': 10, '8': 10, '9': 10, '-': 6, '_': 10, '/': 5, '|': 4, '(': 6, ')': 6,
}
_DEFAULT_W = 10

def pixel_width(text: str) -> int:
    """Estimate SERP pixel width. For meta descriptions scale by ~0.8."""
    return sum(_CHAR_W.get(ch, _DEFAULT_W) for ch in (text or ""))

def metadesc_pixel_width(text: str) -> int:
    return int(pixel_width(text) * 0.8)

def norm_url(base: str, href: str) -> str:
    """Absolute + normalized: lowercase scheme/host, strip fragment, collapse //"""
    absu = urljoin(base, (href or "").strip())
    s = urlsplit(absu)
    path = re.sub(r'/{2,}', '/', s.path) or '/'
    return urlunsplit((s.scheme.lower(), s.netloc.lower(), path, s.query, ''))  # drop fragment  # noqa: E501

def same_registrable_domain(a: str, b: str) -> bool:
    ha, hb = urlparse(a).netloc.lower(), urlparse(b).netloc.lower()
    # crude eTLD+1; replace with `tldextract` in impl for correctness
    return ha.split(':')[0].split('.')[-2:] == hb.split(':')[0].split('.')[-2:]

def is_indexable(p: "object") -> bool:
    if getattr(p, "status", 0) != 200:
        return False
    if 'noindex' in (getattr(p, 'meta_robots', None) or '') or 'noindex' in (getattr(p, 'x_robots', None) or ''):
        return False
    if getattr(p, 'canonical', '') and norm_url(getattr(p, 'url', ''), getattr(p, 'canonical', '')) != getattr(p, 'url', ''):
        return False
    return True

def has_fragment(raw: str | None) -> bool:
    return bool(raw) and '#' in str(raw)

def is_absolute(raw: str | None) -> bool:
    return bool(raw) and bool(urlparse(raw).scheme)

WORD_RE = re.compile(r"\b\w[\w'-]*\b", re.UNICODE)
def word_count(text: str) -> int:
    return len(WORD_RE.findall(text or ""))
