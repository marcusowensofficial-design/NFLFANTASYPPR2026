"""Fetch live multi-book NFL player props consensus from VegasInsider into data/player_props_live.json."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import statistics

from bs4 import BeautifulSoup
import httpx

VEGASINSIDER_URL = "https://www.vegasinsider.com/nfl/odds/player-props/"
CATEGORY_NAMES = ["Touchdowns", "Receiving Yards", "Passing Yards", "Rushing Yards"]


def _parse_cell(cat: str, text: str) -> dict | None:
    s = re.sub(r"\+", " ", text or "").strip() if "o" in (text or "").lower() else (text or "").strip()
    if cat == "Touchdowns":
        m = re.search(r"([+-]?\d{3,5})", (text or "").strip())
        if not m:
            return None
        val = int(m.group(1))
        if abs(val) < 100 or abs(val) > 8500:
            return None
        return {"type": "odds", "odds": f"{val:+d}"}
    m = re.search(r"([ouOU])\s*(\d+(?:\.\d+)?)\s*([+-]\d{3,4})?", text or "")
    if not m:
        return None
    out: dict = {"type": "line", "direction": m.group(1).upper(), "line": float(m.group(2))}
    if m.group(3):
        out["odds"] = m.group(3)
    return out


def sync_live_props(out_path: Path | None = None) -> dict:
    resp = httpx.get(VEGASINSIDER_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=20.0)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.select("table")
    categories: dict[str, list[dict]] = {c: [] for c in CATEGORY_NAMES}
    players: dict[str, dict] = {}

    for idx, cat in enumerate(CATEGORY_NAMES):
        if idx >= len(tables):
            break
        tbl = tables[idx]
        headers = [th.get_text(" ", strip=True) for th in tbl.select("thead th, tr:first-child th")]
        books_cols = [h for h in headers[1:] if h and "›" not in h]
        for tr in tbl.select("tbody tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.select("td,th")]
            if not cells or not cells[0] or "›" in cells[0]:
                continue
            player_name = cells[0].strip()
            books: dict[str, dict] = {}
            lines: list[float] = []
            for bi, bname in enumerate(books_cols):
                if bi + 1 >= len(cells):
                    continue
                parsed = _parse_cell(cat, cells[bi + 1])
                if parsed:
                    books[bname] = parsed
                    if "line" in parsed:
                        lines.append(float(parsed["line"]))
            if not books:
                continue
            consensus_line = round(float(statistics.median(lines)), 1) if lines else None
            entry = {"player": player_name, "category": cat, "consensus_line": consensus_line, "books": books}
            categories[cat].append(entry)
            players.setdefault(player_name, {})[cat] = {"consensus_line": consensus_line, "books": books}

    payload = {
        "source": VEGASINSIDER_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "categories": categories,
        "players": players,
    }
    target = out_path or (Path(__file__).resolve().parent.parent / "data" / "player_props_live.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    res = sync_live_props()
    print({k: len(v) for k, v in res["categories"].items()}, "players=", len(res["players"]), "fetched_at=", res["fetched_at"])
