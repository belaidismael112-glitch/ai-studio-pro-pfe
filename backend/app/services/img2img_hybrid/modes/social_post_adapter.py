from __future__ import annotations

LAYOUTS = ['square_center_card', 'bold_caption_top', 'story_vertical_hero', 'carousel_cover', 'minimal_brand_post', 'promo_badge_layout']
DEFAULT_DENOISE = 0.5
DEFAULT_STEPS = 4
DEFAULT_CFG = 1.0
MODE_MARKER = 'AI_STUDIO_V11_SOCIAL_POST_LAYER'

def choose_layout(category: str, prompt: str, rng):
    text = (prompt or "").lower()
    category = (category or "generic_product").lower()
    weighted = []
    if any(w in text for w in ("story","vertical","tiktok","reel")):
        weighted += ["story_vertical_hero", "bold_caption_top"] * 5
    if any(w in text for w in ("carousel","cover","instagram")):
        weighted += ["carousel_cover", "square_center_card"] * 4
    if any(w in text for w in ("promo","sale","discount","offer")):
        weighted += ["promo_badge_layout", "bold_caption_top"] * 4

    weighted += list(LAYOUTS) * 2
    return rng.choice(weighted or list(LAYOUTS))

def brief(subject: str, category: str, mood: str, user_direction: str, title: str, subtitle: str, cta: str) -> str:
    subject = subject or "uploaded subject"
    category = category or "generic_product"
    mood = mood or "premium commercial"
    user_direction = (user_direction or "").strip()[:260]
    return (
        f"Social media creative for {category}. Preserve the uploaded {subject}. Make a platform-ready post with a bold clean composition, short readable copy zones, and high contrast. "
        f"Use selected social layout only, not a poster template. Mood: {mood}. User direction: {user_direction}. Text: '{title}', '{subtitle}', CTA '{cta}'."
    )

