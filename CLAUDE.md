# NISAARTHI: notes for Claude Code

Night-time safety and route app for late-shift workers (nurses, delivery riders) in India.
Hackathon: Theme 1, Problem 1.1 "The City That Sleeps While You Work". Demo city: **Nagpur**.

## Working rules from the team
- **Don't add features on your own.** Recommend first, build only after the team approves.
- Work in **phases**; finish and test one before starting the next.
- UX must stay simple: one clear job per page.
- UI: dark night-indigo base with a **faded Madhubani print** behind; text always on near-opaque panels so it stays readable. It must look hand-made, not AI-generic.

## Stack
- `mobile/`: React + Vite, wrapped as Android with **Capacitor 6**. Run `npm run dev` for browser, `npm run android` for the device.
- `backend/`: Python + FastAPI. `uvicorn app.main:app --reload`. Tests: `python -m pytest tests`.
- Keys live only in `backend/.env` (see `.env.example`), never in the app.
- Data fallback order everywhere: live → cached copy (labelled by age) → mock → UNKNOWN.
- Every data point carries a confidence label: KNOWN / PROBABLE / OUTDATED / UNKNOWN. Never invent data.

## Phases
| # | Scope | Status |
|---|---|---|
| 1 | Sign-up page (language, name, mobile, 1–5 emergency contacts). No OTP. Token kept on phone, never asks to log in again. Works offline, syncs later. | Done |
| 2 | Trip page: source (current location or search), up to 3 optional stops, destination, departure time, arrival deadline, Search button. Use Geoapify autocomplete. Move sample trip from Pune to Nagpur. Every search dropdown ends with "Choose on map"; search allows ~40 km around Nagpur. | Done (team check pending) |
| 3 | Routes page: all routes ranked by safety score, with traffic (TomTom free tier, fallback to time-of-night estimate labelled PROBABLE), weather, Tavily past incidents per road, Nebius Nemotron safety + feasibility scores, booking links, nearby police stations, siren button. | Planned |
| 4 | Shake opens the app even when closed (native Kotlin foreground service + persistent notification), automatic offline SOS SMS via SEND_SMS, loud siren. | Planned |
| 5 | Feedback: post-trip rating and corrections ("shop was closed", "stretch was dark") that adjust place data and scoring weights. | Planned |
| 6 | Novelty **Rider Eyes**: riders' phones act as moving CCTV; frames → street check → live lighting/activity map used in safety scores. Only scores stored, images deleted, faces never kept. How riders are identified (Settings switch vs sign-up question) is **still to be decided by the team**. | Street check done |
| 7 | 12 regional languages (Hindi, Marathi, Bengali, Tamil, Telugu, Kannada, Malayalam, Gujarati, Punjabi, Odia, Urdu, Assamese) with bundled Noto fonts; hand-drawn Madhubani redesign. | Planned |

## Safety score rules (team requirement)
- Reward **coverage, not count**: share of the route within ~300 m of a place that will be **open at the moment the user reaches it**, plus the longest dark stretch. Diminishing returns per extra shop.
- Example the team gave: Route A with 5 shops spread to the destination beats Route B with 10 shops clustered at the start.
- A shop closing within 10 minutes of arrival counts as risky, not open.
- Rank: safest **feasible** route first (meets the arrival deadline).

## Datasets
- **TrafficCAM** (fixed traffic cameras, 8 Indian cities, day + night): `backend/scripts/download_trafficcam.sh`, then `python scripts/build_street_index.py --night-only --sheet`. No licence file: cite the paper, never commit images (`backend/datasets/` is git-ignored).
  - Unverified: annotation JSON format (reader handles LabelMe and COCO) and city codes other than BLR. Check against real files.
- No public Nagpur CCTV footage exists. Team may record its own Nagpur night clips for the demo (blur faces).

## Open items
- Peer-to-peer feature from the original notes: not defined, not built.
- Nemotron model ID: copy the exact ID from the Nebius Token Factory catalog into `NEBIUS_MODEL`.
- TomTom key needed before Phase 3.
