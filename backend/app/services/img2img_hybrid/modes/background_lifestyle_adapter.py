from __future__ import annotations

LAYOUTS = ['luxury_tabletop', 'studio_gradient', 'urban_lifestyle', 'home_interior', 'outdoor_soft_light', 'premium_showroom']
DEFAULT_DENOISE = 0.46
DEFAULT_STEPS = 4
DEFAULT_CFG = 1.0
MODE_MARKER = 'AI_STUDIO_V11_BACKGROUND_LIFESTYLE_LAYER'

def choose_layout(category: str, prompt: str, rng):
    text = (prompt or "").lower()
    category = (category or "generic_product").lower()
    weighted = []
    if any(w in text for w in ("home","interior","room")):
        weighted += ["home_interior", "premium_showroom"] * 5
    if any(w in text for w in ("outdoor","nature","street","urban")):
        weighted += ["outdoor_soft_light", "urban_lifestyle"] * 5
    if any(w in text for w in ("studio","gradient","clean")):
        weighted += ["studio_gradient", "luxury_tabletop"] * 4

    weighted += list(LAYOUTS) * 2
    return rng.choice(weighted or list(LAYOUTS))

def brief(subject: str, category: str, mood: str, user_direction: str, title: str, subtitle: str, cta: str) -> str:
    subject = subject or "uploaded subject"
    category = category or "generic_product"
    mood = mood or "premium commercial"
    user_direction = (user_direction or "").strip()[:260]
    return (
        f"Background/lifestyle transformation. Preserve the exact {subject}; change only the environment and lighting. No typography, no CTA, no poster cards. "
        f"Scene style follows selected lifestyle layout. Mood: {mood}. User direction: {user_direction}."
    )

