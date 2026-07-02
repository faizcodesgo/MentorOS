# MentorOS

A personal AI mentor: tell it what you want to learn and how much time you have —
it negotiates a realistic plan, builds a day-by-day curriculum, teaches a full
lesson every day, and tracks your progress.

**Phase 1** (this version): goal negotiation → adaptive curriculum → daily lessons → progress tracking.
Coming next: quizzes + spaced repetition, learner memory ("Learning DNA"), projects + AI review,
Android focus mode.

## Run locally

1. Copy `.env.example` to `.env` and paste your free Gemini API key
   (get one at https://aistudio.google.com/apikey).
2. `pip install flask`
3. `python app.py`
4. Open http://localhost:5000

Progress is saved to `mentoros_data.json` locally.

## Deploy (Render)

Push to GitHub → create a Render Blueprint from this repo (`render.yaml` is included) →
set `GEMINI_API_KEY` and `MONGO_URI` in the service's Environment tab.
With `MONGO_URI` set, progress lives in MongoDB Atlas and survives redeploys.

## Stack

Flask (Python) · vanilla HTML/CSS/JS · Gemini API (free tier, plain REST) ·
JSON file storage locally / MongoDB Atlas in production.
