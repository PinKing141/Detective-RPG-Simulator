# Detective's Notebook

A standalone Qt window that displays a beautiful HTML detective notebook with
CSS 3D page-flip animations.

## Files
- `notebook.html` &mdash; the notebook (open it in any browser, or via Qt below)
- `notebook_qt.py` &mdash; PySide6 launcher that opens it in a desktop window

## Run in a browser
Just open `notebook.html`.

## Run as a Qt app
```bash
pip install PySide6
python notebook/notebook_qt.py
```

## Controls
- Click the right half of the book, press &rarr; / Space, or use **NEXT** to flip forward
- Click the left half, press &larr;, or use **PREV** to flip back
- `F11` toggles fullscreen, `Esc` closes

## What's animated
- 3D page flip with `transform: rotateY()` + `backface-visibility` and a soft cubic-bezier ease
- Lamp flicker overlay (`@keyframes flicker`)
- Drifting smoke / atmosphere (`@keyframes smokeDrift`)
- Floating dust motes spawned in JS
- Typewriter text reveal on case notes
- Staggered suspect-list fade-in
- Hover-zoom magnifier on highlighted clues
- Inline content fade-in per spread
