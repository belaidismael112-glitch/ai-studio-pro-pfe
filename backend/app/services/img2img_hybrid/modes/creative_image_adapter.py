from __future__ import annotations

LAYOUTS = ['art_directed_scene', 'surreal_product_world', 'editorial_composite', 'cinematic_reference', 'graphic_campaign', 'premium_moodboard']
DEFAULT_DENOISE = 0.52
DEFAULT_STEPS = 4
DEFAULT_CFG = 1.0
MODE_MARKER = 'AI_STUDIO_V11_CREATIVE_IMAGE_LAYER'

def choose_layout(category: str, prompt: str, rng):
    text = (prompt or "").lower()
    category = (category or "generic_product").lower()
    weighted = []
    if any(w in text for w in ("surreal","fantasy","dream","creative")):
        weighted += ["surreal_product_world", "art_directed_scene"] * 5
    if any(w in text for w in ("cinematic","movie","dramatic")):
        weighted += ["cinematic_reference", "editorial_composite"] * 4
    if any(w in text for w in ("graphic","poster","campaign")):
        weighted += ["graphic_campaign", "premium_moodboard"] * 4

    weighted += list(LAYOUTS) * 2
    return rng.choice(weighted or list(LAYOUTS))

def brief(subject: str, category: str, mood: str, user_direction: str, title: str, subtitle: str, cta: str) -> str:
    subject = subject or "uploaded subject"
    category = category or "generic_product"
    mood = mood or "premium commercial"
    user_direction = (user_direction or "").strip()[:260]
    return (
        f"Creative reference-based image. Preserve the important recognizable elements of {subject}, but allow strong art direction, coherent composition, premium lighting and style transformation. "
        f"Selected creative layout controls composition. Mood: {mood}. User direction: {user_direction}."
    )

