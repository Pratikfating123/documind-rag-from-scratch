"""The ORIGINAL v1 chunker (one chunk per page for pages under 500 words). Used only for comparison."""
import re
_SENT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def _wc(s): return len(s.split())


def chunk_text(text, chunk_size=500, overlap=100):
    sentences = [s.strip() for s in _SENT.split(text) if s.strip()]
    chunks, cur, count, has_new = [], [], 0, False
    for s in sentences:
        w = _wc(s)
        if cur and count + w > chunk_size:
            chunks.append(" ".join(cur))
            carry, carried = [], 0
            for prev in reversed(cur):
                if carried + _wc(prev) > overlap:
                    break
                carry.insert(0, prev); carried += _wc(prev)
            cur, count, has_new = carry, carried, False
        cur.append(s); count += w; has_new = True
    if cur and has_new:
        chunks.append(" ".join(cur))
    return chunks
