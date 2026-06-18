V20 KEEP + OUR ADDITIONS - SAFE MERGE

Base policy:
- V20 fixed pro poster/product engine is preserved.
- rembg is assumed installed and is NOT disabled.
- .env is NOT included and is NOT overwritten.
- V20 installer scripts are NOT included, so this package cannot unexpectedly rewrite .env.
- __pycache__ and .pyc files are excluded.

Included additions:
1) Person / Identity subject coercion:
   person_identity cannot be treated as pet/product/object anymore.
   Expected logs:
   - WORKER_PERSON_IDENTITY_SUBJECT_COERCED old_subject=... new_subject=person_face
   - or WORKER_SOURCE_LOCK_CHECK mode=person_identity subject=person_face

2) Steps cap:
   img2img/person_identity is hard-capped to 4 steps in backend/app/services/ai_service.py.
   Expected Comfy progress: 4/4, not 12/12.

3) Identity board:
   identity diagnostic board/report is OFF by default.
   Final AI output is returned unless the user explicitly requests the report.

4) Neural Camera / Magic Lens additions:
   Full Pro analysis helpers and UI bridges are included.

Install:
- Extract this zip on top of project root.
- Restart backend.
- Restart frontend and remove .next if needed.

Do NOT run the original V20 installer if you want to avoid .env rewrites.
If you already ran it and rembg is installed, that is OK.
