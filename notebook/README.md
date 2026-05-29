# Detective's Notebook

A Qt window that opens with a CRT TV episode-opener, then transitions to a
leather-bound notebook whose four spreads mirror the TUI tabs and are
populated from a **real procedurally-generated case** &mdash; the same one the
terminal UI would show for that `--seed`.

## Files

- `notebook.html` &mdash; the notebook + CRT TV opener (works standalone in a
  browser with placeholder data, or hydrates from injected JSON in Qt)
- `case_dump.py` &mdash; headless case generator. Drives
  `noir.cli.run_game._start_case` (the same path the TUI uses), then
  serializes case-id, episode S/E + title, snapshot, suspects, witnesses,
  victim, evidence, leads, scene POIs, pattern plan, briefing, cold-open,
  partner line, etc. into JSON.
- `notebook_qt.py` &mdash; PySide6 launcher. Runs `build_case_payload(seed)`,
  injects the result via `runJavaScript`, and the page hydrates.

## Run

```bash
pip install PySide6
python notebook/notebook_qt.py --seed 101
python notebook/notebook_qt.py --seed 777 --case-index 1
```

A different `--seed` is a different case &mdash; episode title, location,
victim, suspects, evidence, and POIs all change deterministically. Match the
seed you use in `detective-play --seed N` and the notebook shows the same
case.

## TV opener

- Bezeled CRT TV on a wood console with brass knobs
- Power-on CRT flash, scanlines, vignette, chromatic split, VHS tracking
  band, animated film grain, occasional flicker
- Network tag (`NOIR · CHANNEL 4`), `SEASON N · EPISODE M (SnEm)`, the
  generated episode title in Cinzel serif glow, episode kind
- "PREVIOUSLY ON" recap block when prior cases exist (the same
  `build_previously_on` the TUI uses)
- Staggered cold-open reveal (`build_cold_open`), partner line
  (`build_partner_line`)
- "&#9654; BEGIN INVESTIGATION" power-off (collapses to a horizontal line,
  then a dot) before the notebook fades in

## Notebook spreads

1. **Case File** &mdash; case id, episode banner, "now" line, snapshot
   (district / location / time / pressure / trust / gaze), briefing
   modifiers || **Cold Open**, partner line, victim card, hypothesis line
2. **Leads** &mdash; the lead clocks (witness / CCTV / forensics) with their
   deadlines and action hints || **Scene** &mdash; district + location +
   sketch map of generated POIs and their zones
3. **Profile** &mdash; persons of interest (suspects + witnesses with
   traits) || **Pattern** &mdash; cross-case pattern plan (the TUI's
   Pattern tab)
4. **Evidence Log** &mdash; the full presentation-layer evidence list
   (testimonial / cctv / forensics) with source and confidence band ||
   **Debrief** &mdash; theory state and the arrest reminder

## Controls

- Click left/right half of the book, &larr; / &rarr; / Space, or **PREV / NEXT** buttons
- `F11` fullscreen, `Esc` closes

## Browser fallback

Open `notebook.html` directly in any browser. It renders with a small
"no game data was injected" placeholder so all the animations still work
&mdash; the Qt launcher is what wires real game state in.

## Architecture

```text
case_dump.build_case_payload(seed)
    -> noir.cli.run_game._start_case(...)         # same as TUI/CLI
    -> dict { tv_opener, header, snapshot, victim, suspects, ... }

notebook_qt.NotebookWindow.on_loaded()
    -> view.page().runJavaScript("window.__CASE__ = {...}; window.__hydrate(...);")

notebook.html / window.__hydrate(payload)
    -> renderCaseFile / renderLeads / renderScene / renderProfile /
       renderPatternAndEvidence / renderDebrief + fillTV
```
