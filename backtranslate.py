"""Back-translation check.

You can verify the Greek and the Hebrew. You cannot verify the Finnish, the
Swedish or the Dutch — and those are the quotes most likely to end up in a
footnote, because they are the ones you cannot silently correct while reading.

The check is the standard one: translate the English rendering back into the
source language without showing the model the original, then compare. Where
the round trip diverges materially, the translation is flagged rather than
corrected. A flag is honest; a silent second translation would just be another
unverified rendering sitting on top of the first.

Languages you read are skipped by default. Configure that in
config/backtranslate.yaml rather than editing this file.
"""

import json
import re

from analyze import MODEL, _call
from evidence import jaccard, shingles

PROMPT_VERSION = "backtranslate/1"

# A round trip never returns the same string. Below this, the divergence is
# large enough that the English rendering may have changed the claim.
DIVERGENCE_BELOW = 0.30

SYSTEM = """You translate a single sentence into the target language. You are given only the English text and the target language. You do not have the original.

Return JSON only, no prose, no fences:

{"text": "the sentence in the target language"}

Translate closely rather than idiomatically. This output is used to detect whether an earlier translation shifted a political claim, so preserve hedges, modality, negation, and the strength of the verb exactly. Do not improve the sentence."""

JUDGE_SYSTEM = """You compare two sentences in the same language: an original political statement, and a sentence produced by translating an English rendering of it back into that language.

Report whether the round trip preserved the claim. You are looking for changes that would matter to a researcher quoting this: a hedge added or dropped, negation altered, a modal verb strengthened or weakened, an actor changed, a euphemism resolved into something more explicit or the reverse.

Return JSON only, no fences:

{"preserved": true | false,
 "severity": "none" | "minor" | "material",
 "note": "one sentence naming the specific difference, or empty if none"}

Wording differences that do not change the claim are "none". Only mark "material" where a researcher relying on the English would misstate what was said."""


def _text(data):
    return "".join(b.get("text", "") for b in data.get("content", [])
                   if b.get("type") == "text")


def _json(data):
    t = re.sub(r"^```(?:json)?|```$", "", _text(data).strip(), flags=re.M).strip()
    return json.loads(t)


def back_translate(english, target_lang):
    payload = {"model": MODEL, "max_tokens": 400, "system": SYSTEM,
               "messages": [{"role": "user", "content":
                   f"Target language: {target_lang}\n\nEnglish: {english}"}]}
    try:
        return _json(_call(payload)).get("text", "")
    except Exception:
        return ""


def judge(original, round_trip, lang):
    payload = {"model": MODEL, "max_tokens": 400, "system": JUDGE_SYSTEM,
               "messages": [{"role": "user", "content":
                   f"Language: {lang}\n\nOriginal: {original}\n\n"
                   f"Round trip: {round_trip}"}]}
    try:
        return _json(_call(payload))
    except Exception as e:
        return {"preserved": True, "severity": "none", "note": f"(check failed: {e})"}


def check_item(item, skip_langs):
    """Returns a list of per-quote results, or [] if nothing to check."""
    a = item.get("analysis") or {}
    lang = (item.get("lang") or "").lower()
    if lang in skip_langs:
        return []
    out = []
    for n, q in enumerate(a.get("quotes") or []):
        orig, eng = (q.get("original") or "").strip(), (q.get("translation") or "").strip()
        if not orig or not eng or orig == eng:
            continue
        rt = back_translate(eng, lang or "the source language")
        if not rt:
            continue
        sim = jaccard(shingles(orig, n=3), shingles(rt, n=3))
        verdict = judge(orig, rt, lang) if sim < DIVERGENCE_BELOW else {
            "preserved": True, "severity": "none", "note": ""}
        out.append({
            "quote_index": n, "original": orig, "english": eng,
            "round_trip": rt, "similarity": round(sim, 3),
            "severity": verdict.get("severity", "none"),
            "note": verdict.get("note", ""),
            "flagged": verdict.get("severity") in ("minor", "material"),
        })
    return out


def load_config(path="config/backtranslate.yaml"):
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            c = yaml.safe_load(f)
            return {x.lower() for x in c.get("skip_languages", [])}
    except Exception:
        return set()
