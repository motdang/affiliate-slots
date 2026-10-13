#!/usr/bin/env python3
"""sync.py — slots.json -> each site's copy, and the list of links still to make.

    python3 sync.py            # write every site's slots, fill/empty every HTML marker
    python3 sync.py --check    # report only: what would change, counts by site and brand
    python3 sync.py --list     # write the links-to-make .txt to ~/Desktop/1 — NEXT UP/

slots.json is the one registry. A slot whose url is null renders nothing; a filled one
renders at the site's next build.

Two ways a site takes its slots (sites.<site>.mode):
  json  — sync writes <project>/<file> as {slot: {url, en, th, label_en, label_th}};
          the site's own build reads it and calls its paid() helper per slot.
  html  — the site has no build: sync rewrites the text between
          <!--aff:SLOT--> and <!--/aff:SLOT--> in the listed files.
          <!--aff:SLOT:th--> renders the Thai text and label.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECTS = HERE.parent
REG = json.loads((HERE / "slots.json").read_text(encoding="utf-8"))
NEXT_UP = Path.home() / "Desktop" / "1 — NEXT UP"
LIST_NAME = "AFFILIATE SLOTS — links to make (2026-10-04).txt"


def label(site: dict, lang: str) -> str:
    who = site.get("who_" + lang) or REG["who"][lang]
    out = REG["label"][lang].format(who=who)
    if site.get("label_both") and lang == "en":
        out += " · ลิงก์มีค่าตอบแทน"
    return out


def render(slot: dict, site: dict, lang: str) -> str:
    if not slot.get("url"):
        return ""
    text = slot.get("text_" + lang) or slot["brand"]
    return (f'<a href="{escape(slot["url"])}" rel="sponsored nofollow noopener" target="_blank">{escape(text)}</a>'
            f' <small style="opacity:.75">{escape(label(site, lang))}</small>')


def site_payload(name: str) -> dict:
    site = REG["sites"][name]
    langs = site.get("langs", ["en", "th"])
    out = {"_what": "Paid links, written by affiliate-slots/sync.py from slots.json. Edit there, not here. "
                    "A slot with url null renders nothing.", "slots": {}}
    for lang in langs:
        out["label_" + lang] = label(site, lang)
    for s in REG["slots"]:
        if s["site"] == name:
            row = {"brand": s["brand"], "url": s["url"]}
            for lang in langs:
                row[lang] = s.get("text_" + lang) or s["brand"]
            for k in ("records", "shelves", "prov", "on"):
                if s.get(k):
                    row[k] = s[k]
            out["slots"][s["slot"]] = row
    return out


MARK = re.compile(r"<!--aff:([a-z0-9-]+)(?::(en|th))?-->(.*?)<!--/aff:\1-->", re.S)


def fill_html(path: Path, name: str, write: bool) -> int:
    site = REG["sites"][name]
    by_id = {s["slot"]: s for s in REG["slots"] if s["site"] == name}
    src = path.read_text(encoding="utf-8")

    def sub(m: re.Match) -> str:
        slot_id, lang = m.group(1), m.group(2) or site.get("lang", "en")
        s = by_id.get(slot_id)
        body = render(s, site, lang) if s else ""
        if body:
            body = " " + body
        tag = f"{slot_id}:{m.group(2)}" if m.group(2) else slot_id
        return f"<!--aff:{tag}-->{body}<!--/aff:{slot_id}-->"

    new = MARK.sub(sub, src)
    if new != src and write:
        path.write_text(new, encoding="utf-8")
    return int(new != src)


def sync(write: bool) -> None:
    changed = []
    for name, site in REG["sites"].items():
        root = PROJECTS / site["project"]
        if site["mode"] == "json":
            p = root / site["file"]
            new = json.dumps(site_payload(name), ensure_ascii=False, indent=1) + "\n"
            old = p.read_text(encoding="utf-8") if p.exists() else ""
            if new != old:
                changed.append(str(p))
                if write:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(new, encoding="utf-8")
        else:
            for f in site["files"]:
                if fill_html(root / f, name, write):
                    changed.append(str(root / f))
    print(("wrote" if write else "would change"), len(changed))
    for c in changed:
        print("  ", c)


def counts() -> None:
    by_site, by_brand, live = Counter(), Counter(), Counter()
    for s in REG["slots"]:
        by_site[s["site"]] += 1
        by_brand[s["brand"]] += 1
        live[s["site"]] += bool(s["url"])
    for k in sorted(by_site):
        print(f"{k}: {by_site[k]} slots, {live[k]} filled")
    print("brands:", ", ".join(f"{k} {v}" for k, v in by_brand.most_common()))


def write_list() -> Path:
    todo = [s for s in REG["slots"] if not s["url"] and not s.get("off")]
    seen, lines = set(), []
    for s in todo:
        key = (s["brand"], s["destination"], s["sub_id"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(f'{s["brand"]} — {s["destination"]} — Sub ID {s["sub_id"]}')
    head = [f"{len(lines)} links to make in Travelpayouts (Tools → Links: destination URL + Sub ID). "
            "Paste each finished tpx.li link into the url field of the same Sub ID in "
            f"{HERE / 'slots.json'}, then run python3 \"{HERE / 'sync.py'}\" and rebuild that site.", ""]
    fix = REG.get("replace", [])
    if fix:
        lines += ["", f"{len(fix)} existing links land on a page that answers 404; the same Sub ID, the new destination:"]
        lines += [f'{f["brand"]} — {f["destination"]} — Sub ID {f["sub_id"]} (replaces {f["old"]}, used on {f["used_on"]})' for f in fix]
    p = NEXT_UP / LIST_NAME
    p.write_text("\n".join(head + lines) + "\n", encoding="utf-8")
    return p


if __name__ == "__main__":
    if "--list" in sys.argv:
        print(write_list())
    elif "--check" in sys.argv:
        sync(False)
        counts()
    else:
        sync(True)
        counts()
