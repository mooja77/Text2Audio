"""Licence manifest served by GET /api/licenses.

The rows come straight from the ``## Summary`` table in docs/LICENSES.md, the
verified record, so there is no second hand-maintained list. Rows that are not
used by the app (proposed alternatives, data it never loads) are left out.
"""
import re
from pathlib import Path

LICENSES_MD = Path(__file__).resolve().parent.parent / "docs" / "LICENSES.md"

_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_VERDICT = re.compile(r"ALLOWED-WITH-CONDITIONS|ALLOWED|BLOCKED|UNRESOLVED")
_NOT_IN_USE = ("Proposed", "Not used")


def _plain(cell: str) -> str:
    cell = _LINK.sub(r"\1", cell)
    return cell.replace("**", "").replace("`", "").strip()


def load_components(path: Path = LICENSES_MD) -> list[dict]:
    """Components in use, each with licence, verdict and a source link."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out, inside = [], False
    for line in lines:
        if line.startswith("## "):
            inside = line.strip() == "## Summary"
            continue
        if not inside or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0] == "Component" or set(cells[0]) <= set("-: "):
            continue
        used = _plain(cells[1])
        if used.startswith(_NOT_IN_USE):
            continue
        name = _plain(cells[0])
        licence = _plain(cells[2])
        verdict = _plain(cells[3])
        match = _VERDICT.search(verdict)
        link = _LINK.search(cells[4])
        if link:
            url = link.group(2)
        elif cells[4] == "PyPI JSON":
            url = f"https://pypi.org/project/{name.split()[0]}/"
        else:
            url = None
        out.append({"name": name, "usedFor": used, "license": licence,
                    "verdict": match.group(0) if match else verdict,
                    "commercial": "-NC-" not in licence.upper(), "link": url})
    return out
