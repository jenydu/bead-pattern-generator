"""Every UI string must exist in English and Chinese, with the same {placeholders}."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def load():
    src = (WEB / "i18n.js").read_text(encoding="utf-8")
    out = {}
    for lang in ("en", "zh"):
        block = re.search(rf"\n  {lang}: {{\n(.*?)\n  }},", src, re.S).group(1)
        out[lang] = dict(re.findall(r'^    (\w+): "((?:[^"\\]|\\.)*)",$', block, re.M))
    return out


def test_languages_have_the_same_keys():
    d = load()
    assert d["en"] and set(d["en"]) == set(d["zh"])


def test_placeholders_match():
    d = load()
    for key, en in d["en"].items():
        assert set(re.findall(r"\{(\w+)\}", en)) == set(re.findall(r"\{(\w+)\}", d["zh"][key])), key


def test_every_key_used_in_the_page_exists():
    d = load()
    used = set()
    for name in ("index.html", "app.js", "viewer.js"):
        text = (WEB / name).read_text(encoding="utf-8")
        used |= set(re.findall(r'data-i18n="(\w+)"', text))
        used |= set(re.findall(r'data-i18n-attr="[^"]*?:(\w+)', text))
        used |= set(re.findall(r'\bt\("(\w+)"', text))
        used |= set(re.findall(r';(?:\w[\w-]*):(\w+)"', text))
    missing = {k for k in used if k not in d["en"] and not k.startswith("brand_")}
    assert not missing, missing
