def select_renderer(mode: str, analysis) -> str:
    if mode == "flyer_poster":
        return "deterministic_flyer"
    if mode in {"product_ad", "background_replace"}:
        return "hybrid"
    if mode in {"person_identity", "creative_image"}:
        return "comfy"
    return "hybrid"
