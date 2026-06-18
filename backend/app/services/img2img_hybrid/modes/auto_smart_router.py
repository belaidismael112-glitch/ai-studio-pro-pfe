from __future__ import annotations

AUTO_SMART_ROUTER_MARKER = "AI_STUDIO_V11_AUTO_SMART_ROUTER"

def route(requested_mode: str, subject_type: str, category: str, prompt: str, contains_person: bool=False) -> tuple[str, str]:
    mode = (requested_mode or "auto").lower().replace("-", "_")
    text = (prompt or "").lower()
    if mode != "auto":
        if mode == "person":
            return "person_identity", "explicit person alias"
        if mode == "social":
            return "social_post", "explicit social alias"
        return mode, "explicit mode"
    if contains_person or subject_type == "person" or any(w in text for w in ("portrait","headshot","identity","linkedin","person")):
        return "person_identity", "person/identity intent"
    if any(w in text for w in ("background","replace background","scene","lifestyle","environment","decor")):
        return "background_replace", "background/lifestyle intent"
    if any(w in text for w in ("instagram","social","post","story","reel","carousel","facebook","tiktok")):
        return "social_post", "social post intent"
    if any(w in text for w in ("flyer","poster","cta","shop now","headline","campaign poster")):
        return "flyer_poster", "flyer/poster intent"
    if any(w in text for w in ("ad","advertisement","product ad","ecommerce","offer","sale","promo")):
        return "product_ad", "product ad intent"
    if subject_type == "product" or category not in {"person", "document"}:
        return "product_ad", "default product ad"
    return "creative_image", "default creative image"
