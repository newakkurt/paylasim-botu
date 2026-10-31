import json
import re


def make_platform_variants(content, ask_fn):
    """Turn an approved nature X post into ready-to-review Instagram and LinkedIn copy."""
    source = str(content.get("check_text") or content.get("text") or "").strip()
    source_url = (content.get("src") or {}).get("url", "")
    prompt = f"""Repurpose this approved nature/science social post for two different platforms.
Approved source post:
{source}
Source URL (include only if useful): {source_url}
Return ONLY JSON with keys instagram_caption and linkedin_post.
Instagram rules: natural engaging caption, 2-4 short paragraphs, one question or save/share CTA, at most 5 relevant hashtags, max 1800 characters.
LinkedIn rules: professional educational tone, 3-5 concise sentences, one practical takeaway, end with one thoughtful question, at most 3 hashtags, max 1300 characters.
Accuracy: preserve the source meaning. Do not add facts, statistics, dates, species claims or personal experiences not present in the approved source. Do not copy the X post word-for-word. No fabricated citations."""
    fallback_ig = (
        source.replace("#", "").strip()
        + "\n\nSave this nature fact and share your thoughts.\n#Nature #Wildlife #Science"
    )[:1800]
    fallback_li = (
        source.replace("#", "").strip()
        + "\n\nWhat does this teach us about the natural world?"
    )[:1300]
    try:
        raw = ask_fn(prompt, as_json=True, tier="fast")
        data = json.loads(raw)
        instagram = re.sub(r"\n{3,}", "\n\n", str(data.get("instagram_caption") or "").strip())
        linkedin = re.sub(r"\n{3,}", "\n\n", str(data.get("linkedin_post") or "").strip())
        if not 80 <= len(instagram) <= 1800:
            instagram = fallback_ig
        if not 80 <= len(linkedin) <= 1300:
            linkedin = fallback_li
        return {"instagram_caption": instagram, "linkedin_post": linkedin}
    except Exception as exc:
        print("Cross-platform copy generation fallback:", str(exc)[:180])
        return {"instagram_caption": fallback_ig, "linkedin_post": fallback_li}
