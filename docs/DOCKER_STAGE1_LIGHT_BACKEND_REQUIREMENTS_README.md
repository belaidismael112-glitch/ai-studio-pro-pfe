# Docker Stage 1 - light backend requirements

This patch stops the backend Docker build from installing GPU/CUDA packages.

Why: Stage 1 keeps ComfyUI and Ollama outside Docker, so the backend container does not need `torch`, `scipy`, `scikit-image`, or `numba` during the first Docker pass.

Install:
1. Stop the current build with Ctrl+C.
2. Run `docker compose down`.
3. Extract this zip over the project root.
4. Run `docker compose build --no-cache backend`.
5. Then run `docker compose build --no-cache webapp`.
6. Then run `docker compose up`.

If the backend later fails at runtime with a missing ML package, add a CPU-only package deliberately instead of allowing CUDA packages to install implicitly.
