AI Studio V21 - Pro Comfy Poster Background

Purpose:
- V20 was technically correct but too standard because Flyer/Poster used a deterministic fixed background.
- V21 forces Flyer/Poster and Social Post to use a real Comfy-generated premium poster background.
- The exact uploaded product is still isolated and composited by backend so labels/shape remain source locked.
- Backend still renders readable text; Comfy does not draw text.

Expected log:
- V21_PRO_COMFY_POSTER_SUCCESS
- renderer_version='v21-pro-comfy-poster-background'
- v21_marker='AI_STUDIO_V21_PRO_COMFY_POSTER_BACKGROUND'
- v21_background_ai=True
- v21_pro_comfy_poster_background=True
- v20_fixed_pro_stage_background=False
- v20_text_rendered=True

Do not install V18/V19/V20 over this after installation.
