# PrepAI — Your AI-Powered Board Exam Partner

PrepAI is a full-stack Django platform for Indian students preparing for board examinations (CBSE, ICSE and state boards). Students pick their board, class, subject and chapter, then study notes, solve question papers and previous-year papers, take timed tests, track performance, scan questions with AI, and chat with an AI study assistant.

All educational content (boards, classes, subjects, chapters, topics, questions, papers, tests, materials) is **data**, managed in Django Admin. There are no hard-coded boards or subjects in the code.

---

## 1. Project overview

| Layer | What it does |
|---|---|
| Django templates + Bootstrap 5.3 | Responsive UI with light/dark themes, reusable components |
| Django REST Framework | Versioned REST API at `/api/v1/` (session + token auth) |
| PostgreSQL | Primary database (SQLite fallback for quick local runs) |
| `services/ai_service.py` | Provider-agnostic AI layer (Anthropic Claude by default) |
| `services/ocr_service.py` | Optional OCR step for the scanner (vision model or Tesseract) |
| Django Admin | Complete content workflow with publish/unpublish |

### App layout

```
config/           settings, root URLs, API router, WSGI/ASGI
core/             base models, validators, permissions, home, error pages, template tags, seed command
accounts/         custom User (email login), Profile, auth views, auth API
boards/           Board → ClassLevel → Subject → Chapter → Topic + board explorer
questions/        Question bank, options, concepts, historical appearances, frequency analysis
papers/           Question papers, previous-year papers (proxy model), PDF viewer/download
content/          Study material library
testengine/       Tests, attempts, answers, grading, results   (the spec's "tests" app*)
bookmarks/        Generic bookmarks
analytics/        Activity log, performance records, analytics queries
recommendations/  Rule-based recommendation engine
notifications/    Notifications + admin announcements
search/           Global search, suggestions, search history
scanner/          AI question scanner + scan history
assistant/        AI study assistant conversations
dashboard/        Student dashboard + analytics pages
services/         ai_service.py, ocr_service.py (no views; pure service layer)
templates/ static/ media/
```

\* Named `testengine` because a top-level package called `tests` collides with Python/Django test discovery.

## 2. Features

- **Board explorer** — Board → Class → Subject → Chapter → Topic, each page showing materials, questions, tests and previous-year questions.
- **Question papers & previous-year papers** — filters (board, class, subject, chapter, year, paper/exam type, difficulty), in-browser PDF viewer (zoom, page navigation, fullscreen, lazy rendering), download, bookmark, share, related papers, and important questions ranked by historical frequency.
- **Online test engine** — chapter, subject, board, previous-year, practice and full-length mock tests. Timer with automatic submission, question palette, mark for review, clear answer, negative marking, autosave with an offline backup (answers survive refreshes and network drops), server-side deadline enforcement, and detailed results (score, accuracy, time, question-wise review, subject/chapter breakdown, recommended topics and tests).
- **AI Question Scanner** — camera capture or upload (drag/drop/paste), printed or handwritten. It detects the question, subject and chapter, then gives the answer, step-by-step explanation, concept and follow-up questions. Scans are saved to history for logged-in users; failures offer a retry.
- **AI Study Assistant** — conversation history, modes (simple, detailed, practice questions, quiz, revision), subject context, Markdown and LaTeX rendering.
- **Question Prediction & Frequency Analysis** — previous appearances, frequency, recency, repeated concepts, similar questions and a transparent preparation priority, computed **only** from stored papers. The disclaimer "Historical analysis does not guarantee appearance in a future examination." is always shown.
- **Exam Question Predictor** (`/questions/predictor/`) — paste any question, or send one from the AI Scanner. PrepAI matches it to stored questions (exact repeats and reworded versions), shows **how many times** it appeared, **in which years** and in which papers (a year-by-year timeline), finds the **recurrence pattern** (e.g. "about every 2 years → next around 2027"), and gives a **history-based likelihood estimate** for the upcoming exam. The estimate uses a transparent formula (appearance rate 60%, recency 25%, concept rate 15%, +5 points if the pattern points to the upcoming year), is capped between 3% and 85%, and always shows the disclaimer. Its accuracy depends on how many real previous-year papers are loaded.
- **Dashboard & analytics** — tests attempted, average and best score, questions solved, study streak, subject/chapter/test-type performance, score trend (Chart.js), weak and strong areas, recent activity, bookmarks, scans and conversations.
- **Recommendations** — weak chapters trigger revision notes, chapter tests, frequently repeated questions and previous-year papers; new students get picks for their board and class.
- **Global search** — 10 result categories, board/class/subject/chapter/year/type filters, suggestions, recent searches, search history.
- **Bookmarks, notifications, announcements, profiles and preferences** (language, theme, explanation style, study goals).

## 3. Technology stack

Python 3.12+ · Django 5.2/6.0 · Django REST Framework · django-filter · PostgreSQL (psycopg 3) · Bootstrap 5.3 + Bootstrap Icons · Chart.js · PDF.js · KaTeX · WhiteNoise · Anthropic Python SDK.

## 4. Installation

```bash
git clone <your-repo-url> prepai && cd prepai
```

## 5. Python virtual environment setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 6. PostgreSQL setup

```sql
-- psql -U postgres
CREATE DATABASE prepai;
CREATE USER prepai WITH PASSWORD 'change-me';
ALTER DATABASE prepai OWNER TO prepai;
```

Then set `DATABASE_URL=postgres://prepai:change-me@localhost:5432/prepai` in `.env`.
For a quick local trial you can leave `DATABASE_URL` empty to use SQLite (not for production).

## 7. Environment variables

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

| Variable | Purpose |
|---|---|
| `DEBUG` | `True` locally, `False` in production |
| `SECRET_KEY` | Required when `DEBUG=False`. Generate: `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Comma-separated hostnames / origins |
| `DATABASE_URL` | PostgreSQL URL (empty → SQLite) |
| `REDIS_URL` | Optional cache (install `redis`) |
| `AI_PROVIDER` | `anthropic` \| `groq` \| `openrouter` \| `openai_compatible` \| `mock` \| `disabled` |
| `AI_API_KEY`, `AI_MODEL`, `AI_VISION_MODEL`, `AI_BASE_URL`, `AI_TIMEOUT`, `AI_MAX_TOKENS`, `AI_EFFORT`, `AI_REFUSAL_FALLBACK` | AI configuration (section 13) |
| `OCR_BACKEND` | `vision_llm` \| `tesseract` \| `none` |
| `THROTTLE_*` | API rate limits (e.g. `60/hour`) |
| `MAX_PDF_UPLOAD_MB`, `MAX_IMAGE_UPLOAD_MB` | Upload limits |
| `STORAGE_BACKEND` + `AWS_*` | `local` or `s3` media storage |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | Email (password reset). The console backend prints emails to the terminal |
| `GOOGLE_OAUTH_CLIENT_ID/SECRET` | Optional Google sign-in (see below) |

No secret is hard-coded anywhere; all configuration is read in `config/settings.py`.

## 8. Database migration

```bash
python manage.py migrate
```

## 9. Creating a superuser

```bash
python manage.py createsuperuser     # asks for email, username and password
```

Admin is at `/admin/`.

## 10. Running the development server

```bash
python manage.py runserver
```

Open http://localhost:8000.

## 11. Loading sample data

```bash
python manage.py seed_demo            # idempotent
python manage.py seed_demo --reset    # remove existing sample content first
```

This creates 9 boards (CBSE, ICSE, Maharashtra, Gujarat, Karnataka, Tamil Nadu, UP, Bihar, West Bengal), classes, subjects, chapters, topics, 30 questions, demo papers with generated PDFs, 8 tests, study material, an announcement, and a demo student:

- **Email:** `student@prepai.local`
- **Password:** `demo-student-2026`

The demo student has three completed attempts, so the dashboard, analytics and recommendations are populated.

> **All seeded content is flagged `is_sample=True` and shows a "Sample" badge.** Demo "previous-year" papers are titled `[Demo] … (sample previous-year format)`, state that they are not official board papers, and exist only to demonstrate the frequency analysis. Do not present them as real examination statistics. Replace them with real papers before launch.

## 12. Running tests

```bash
python manage.py test
```

63 tests cover the question predictor (matching, years, bounded estimates, patterns, API), grading (MCQ, multi-select, numeric, fill-in-the-blank, subjective), negative marking, deadlines and auto-submit, attempt limits, answer-leak prevention, per-user access control, frequency analysis correctness and disclaimers, AI failure handling (503 plus friendly message, rollback), the Anthropic and Groq/OpenRouter request shapes (mocked SDKs, no network), scanner upload validation, guest scans, accounts and token auth, bookmarks, search filters and recommendations.

## 13. AI API configuration

All AI calls go through `services/ai_service.py`. Views never call an SDK directly.

```env
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...        # or leave empty and set ANTHROPIC_API_KEY
AI_MODEL=claude-opus-5
AI_TIMEOUT=90
AI_EFFORT=                   # optional: low | medium | high | xhigh | max
AI_REFUSAL_FALLBACK=True
```

- **Default model** is `claude-opus-5`. Any Claude model ID can be set in `AI_MODEL`.
- **Groq, OpenRouter or any OpenAI-compatible API:**
  ```env
  AI_PROVIDER=groq            # or: openrouter
  AI_API_KEY=your-provider-key
  AI_MODEL=                   # optional: text model (empty = preset default)
  AI_VISION_MODEL=            # optional: model used by the scanner for images
  ```
  `groq` and `openrouter` fill in the base URL and default Llama models. For another provider (Together, a self-hosted vLLM/Ollama server, etc.) use `AI_PROVIDER=openai_compatible` and set `AI_BASE_URL`. The scanner needs a model that accepts images, and these providers don't enforce the JSON schema, so the response is parsed and fitted to the expected fields. Model IDs change often, so check your provider's model list if you see "model not found".
- **Refusal fallback:** for `claude-opus-5` (and `claude-fable-5-1`), requests use the server-side fallback beta (`fallbacks="default"`), so a declined request is retried on a fallback model within the same call. Set `AI_REFUSAL_FALLBACK=False` to turn it off.
- **Scanner** uses structured JSON output (`output_config.format`) and sends images as base64 content blocks, downscaled to at most 1568 px and EXIF-rotated.
- **Failures** (auth, rate limit, timeout, network, refusal) become `AIServiceError`. The API returns HTTP 503 with `"AI service is temporarily unavailable. Please try again."` (or a more specific safe message), and the UI shows a retry button. The site never crashes because of the AI.
- **Offline development:** `AI_PROVIDER=mock` returns clearly labelled placeholder responses, so every AI screen works without a key. `disabled` hides AI features behind a friendly notice.
- **Adding a provider:** subclass `BaseAIProvider`, implement `complete()`, and register it in `_PROVIDERS`.
- **OCR:** `OCR_BACKEND=vision_llm` (default) lets the vision model read the image. `tesseract` runs Tesseract first (install `pytesseract` and the binary) and passes the text as a hint.
- **Rate limits:** `THROTTLE_AI_ASSISTANT` and `THROTTLE_AI_SCANNER` cap AI usage per user/IP.

## 14. Media / PDF configuration

- Uploads are validated by **content**: PDFs must start with `%PDF-`, and images must decode with Pillow (JPG/PNG/WEBP/GIF). Size limits come from `MAX_*_UPLOAD_MB`.
- Local storage writes to `media/`. In development Django serves it; in production serve `/media/` from your web server or use S3.
- **S3:** `pip install django-storages[s3]`, set `STORAGE_BACKEND=s3` and the `AWS_*` variables. PDF downloads then redirect to signed URLs instead of streaming through Django.
- PDFs are viewed with PDF.js through a same-origin endpoint (`/papers/<slug>/file/`), which counts views and downloads.

## 15. Deployment instructions

1. Set `DEBUG=False`, a strong `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` (PostgreSQL), `REDIS_URL` (recommended), email and AI settings.
2. `pip install -r requirements.txt`
3. `python manage.py migrate`
4. `python manage.py collectstatic --noinput` (WhiteNoise serves hashed, compressed assets)
5. `python manage.py check --deploy` (it passes with the provided settings)
6. Run with Gunicorn behind Nginx or a platform load balancer:
   ```bash
   gunicorn config.wsgi:application --workers 3 --timeout 120
   ```
   Use a timeout above `AI_TIMEOUT`, because scanner and assistant requests wait for the AI.
7. With `DEBUG=False`, HTTPS redirect, secure cookies and 1-year HSTS are on by default. Forward `X-Forwarded-Proto` from your proxy.
8. Health check endpoint: `GET /healthz/` (returns 503 if the database is unreachable).

**Google authentication (optional):** the login page shows "Continue with Google" when `GOOGLE_OAUTH_CLIENT_ID` is set. To enable it, install `django-allauth`, add its apps, backend and URLs (`/accounts/google/login/`), and keep `EmailOrUsernameBackend` in `AUTHENTICATION_BACKENDS`. The rest of the app needs no changes because users are keyed by email.

## 16. Future scalability

- **Background jobs:** move notification fan-out (`notifications/services.py`), recommendation regeneration and AI scans to Celery/RQ. Callers already go through service functions.
- **Search:** `search/services._text_filter` can be swapped for PostgreSQL full-text search (`SearchVector`/`SearchRank` with GIN indexes), or for OpenSearch/Meilisearch, without changing views.
- **Streaming AI replies:** add a streaming endpoint (SSE) around the provider interface for long answers.
- **Recommendations:** the rule-based engine keeps a `reason` per item. An ML ranker can replace `generate_for_user` behind the same interface.
- **Caching:** navigation boards and homepage stats are cached. Enable Redis and add per-view caching for public pages.
- **New boards and languages:** all curriculum is admin data. UI strings are ready for Django i18n (`USE_I18N=True`), and profiles already store a preferred language that the AI assistant respects.
- **Mobile apps:** the REST API supports token authentication (`/api/v1/auth/login/`).

---

## API quick reference (`/api/v1/`)

| Endpoint | Methods | Notes |
|---|---|---|
| `auth/register/`, `auth/login/`, `auth/logout/`, `auth/me/`, `auth/change-password/`, `auth/theme/` | POST / GET / PATCH | Token + session auth |
| `boards/`, `classes/`, `subjects/`, `chapters/`, `topics/` | GET (staff: write) | Filters e.g. `?board=`, `?class_level=` |
| `questions/`, `questions/{id}/frequency/` | GET | Historical frequency analysis |
| `questions/predict/` | POST `{"text", "board"?, "class_level"?, "subject"?}` | Times appeared, years, papers, pattern, likelihood estimate |
| `papers/`, `previous-year-papers/`, `…/{slug}/important-questions/` | GET | Filters: subject, year, type… |
| `materials/` | GET | |
| `tests/`, `tests/{slug}/start/` | GET / POST | |
| `attempts/`, `attempts/{id}/questions/`, `…/answer/`, `…/submit/`, `…/result/` | GET / POST | Owner only; no answers leaked before submit |
| `bookmarks/`, `bookmarks/toggle/` | GET / POST / DELETE | |
| `scanner/` | POST (multipart `image` or `question`), GET history | Throttled |
| `assistant/conversations/`, `…/{id}/messages/` | CRUD / POST | Throttled |
| `dashboard/`, `recommendations/`, `recommendations/{id}/dismiss/` | GET / POST | |
| `notifications/`, `…/{id}/read/`, `…/read-all/`, `…/unread-count/` | GET / POST | |
| `search/`, `search/suggestions/`, `search/history/` | GET / DELETE | |

Errors always look like `{"error": {"message": "...", "code": "...", "details": ...}}`.
