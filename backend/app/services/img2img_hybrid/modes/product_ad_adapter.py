from __future__ import annotations

LAYOUTS = ['product_hero_center', 'premium_packshot_shadow', 'split_product_offer', 'floating_product_stage', 'dark_luxury_ad', 'minimal_ecommerce_ad']
DEFAULT_DENOISE = 0.42
DEFAULT_STEPS = 4
DEFAULT_CFG = 1.0
MODE_MARKER = 'AI_STUDIO_V11_PRODUCT_AD_LAYER'

def choose_layout(category: str, prompt: str, rng):
    text = (prompt or "").lower()
    category = (category or "generic_product").lower()
    weighted = []
    if category in {"watch", "tech"} or any(w in text for w in ("dark","luxury","premium","black")):
        weighted += ["dark_luxury_ad", "premium_packshot_shadow", "floating_product_stage"] * 4
    if any(w in text for w in ("minimal","clean","ecommerce","catalog")):
        weighted += ["minimal_ecommerce_ad", "product_hero_center"] * 4
    if any(w in text for w in ("sale","offer","promo","discount")):
        weighted += ["split_product_offer", "floating_product_stage"] * 4

    weighted += list(LAYOUTS) * 2
    return rng.choice(weighted or list(LAYOUTS))

def brief(subject: str, category: str, mood: str, user_direction: str, title: str, subtitle: str, cta: str) -> str:
    subject = subject or "uploaded subject"
    category = category or "generic_product"
    mood = mood or "premium commercial"
    user_direction = (user_direction or "").strip()[:260]
    return (
        f"Commercial product advertisement for {category}. Preserve the exact {subject}; do not redesign product, logo, material, or proportions. "
        f"Selected product-ad layout must define a real ad composition: hero product, premium background, shadow, offer/claim zone if needed. "
        f"Mood: {mood}. User direction: {user_direction}. Use very little text unless requested: headline '{title}', CTA '{cta}'."
    )

