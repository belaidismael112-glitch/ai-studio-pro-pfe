# Motion / Sequence Direction

Implemented as a scroll-linked 120-frame canvas sequence.

Frame logic:
- Frames 0-20: assembled / centered / stable.
- Frames 21-55: precision expand / widening cues.
- Frames 56-85: layer opening moment.
- Frames 86-119: magnetic glide back to assembled state.

Technical implementation:
- Next.js App Router page in `src/app/page.tsx`.
- Canvas renderer in `src/components/KeyboardScroll.tsx`.
- 120 frames in `public/keyboard-sequence`.
- Framer Motion `useScroll` maps scroll progress to frames 0-119.
- Canvas handles `devicePixelRatio`, resize, contain-fit drawing, requestAnimationFrame, and redundant draw prevention.
