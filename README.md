# Bookly Support Agent

Bookly is a book discovery and recommendation platform. This project is a chat-based AI customer service agent built with FastAPI and Claude, allowing customers to get help with their orders, payments, refunds, and general platform questions.

## Features

- **AI-powered chat** — Conversational support agent powered by Claude
- **Order lookup** — Customers can view their order history and individual order details
- **Payment information** — Customers can check payment breakdowns for any order
- **Refund processing** — Eligible orders (pending status) can be refunded through the chat
- **Help center** — Agent answers general questions about shipping, returns, gift cards, and more
- **Session memory** — Agent remembers who the customer is throughout the conversation
- **Authorization** — Customers can only access their own orders and payment data

## Tech Stack

- **Backend** — Python, FastAPI
- **AI** — Anthropic Claude (`claude-sonnet-4-6`) via the Anthropic SDK
- **Database** — SQLite
- **Frontend** — Vanilla HTML/CSS/JS served by FastAPI

## Project Structure

```
bookly-demo/
├── app/
│   ├── main.py          # FastAPI app and routes
│   ├── agent.py         # Claude agent and tool loop
│   ├── tools.py         # Tool definitions and implementations
│   ├── database.py      # SQLite schema and connection
│   ├── sessions.py      # In-memory session store
│   ├── seed.py          # Database seed script
│   └── static/
│       └── index.html   # Chat UI
├── data/
│   └── help_center.txt  # Bookly policy documentation
├── .env.example
├── requirements.txt
└── README.md
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/mdthakker/bookly-demo.git
cd bookly-demo
```

### 2. Add your Anthropic API key

```bash
cp .env.example .env
```

Open `.env` and replace `your_api_key_here` with your key from [console.anthropic.com](https://console.anthropic.com).

### 3. Run the startup script

```bash
bash start.sh
```

This will create a virtual environment, install dependencies, seed the database, and start the server.

Once running, open [http://localhost:8000](http://localhost:8000) in your browser.

## Startup Script

`bash start.sh` handles the full setup: it creates `.venv` if missing, installs
dependencies, seeds the database on first run, and starts the server.

The script invokes the virtualenv interpreter by path (`.venv/bin/python`), so it
works from any directory and does not require the virtualenv to be activated in
your shell first.

### Running without the startup script

Dependencies are installed only inside `.venv`, never globally. Use the venv
interpreter explicitly:

```bash
.venv/bin/python -m uvicorn app.main:app --reload
```

Or activate the virtualenv first, then use plain `python3`:

```bash
source .venv/bin/activate
python3 -m uvicorn app.main:app --reload
```

Running `python3 -m uvicorn app.main:app` with the system interpreter will not
work -- the app exits with a message telling you which interpreter to use.

## Deploying to Vercel

The app runs on Vercel with no code changes. Vercel resolves `app/main.py` as the
ASGI entrypoint automatically (it looks for `main.py` inside `app/`, exporting a
top-level `app`), so the whole API builds into one Vercel Function.

```bash
npm i -g vercel
vercel          # preview deploy
vercel --prod   # production
```

Set these in **Project Settings -> Environment Variables** (`.env` is gitignored
and is not uploaded):

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required. Claude API access. |
| `ARIZE_API_KEY` | Optional. Enables Arize tracing. |
| `ARIZE_SPACE_ID` | Optional. Enables Arize tracing. |
| `ARIZE_PROJECT_NAME` | Optional. Defaults to `bookly-support-agent`. |

Config in the repo:

- `vercel.json` — sets `maxDuration` to 60s for `app/main.py`, since an agent
  turn with tool calls takes longer than a plain request.
- `.python-version` — pins Python 3.14 to match local development.
- `.vercelignore` — keeps the virtualenv, caches, and stray `.db` files out of
  the bundle.

### Why it works on a read-only filesystem

Serverless filesystems are read-only and instances are ephemeral, so the demo
holds no durable state:

- The database is **in-memory**, seeded on first use. Every cold start begins
  from identical data.
- `process_refund` **validates but does not persist**, so a refund-eligible
  order stays eligible and repeated evaluation runs cannot contaminate
  each other.
- Spans use `SimpleSpanProcessor`, exporting as each span ends rather than
  batching in a background thread that a frozen instance would never flush.

## Invoking the Agent Remotely

`POST /chat` is the whole API — the browser UI is just one client of it.

```bash
curl -X POST https://<your-deployment>.vercel.app/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "row-1",
       "auth_token": "david@example.com",
       "messages": [{"role": "user", "content": "What are my orders?"}]}'
```

```json
{"response": "You have 2 orders: #8 shipped ($32.98), #7 pending ($18.99)."}
```

| Field | Required | Notes |
|---|---|---|
| `messages` | yes | Full conversation history; `[{role, content}]`. |
| `session_id` | yes | Any string. Scopes server-side session context. |
| `auth_token` | no | Customer identity (an email, in this mock). Omit and the agent asks. |
| `stream` | no | `true` returns `text/event-stream`. |

Because identity is a request field, an evaluation dataset can carry it as a
column next to the query. `examples/invoke_agent.py` has a ready task function
and a sample dataset:

```bash
BOOKLY_URL=https://<your-deployment>.vercel.app python examples/invoke_agent.py
```

## Sample Customers (Seed Data)

| Name | Email |
|---|---|
| Alice Monroe | alice@example.com |
| Ben Carter | ben@example.com |
| Clara Diaz | clara@example.com |
| David Kim | david@example.com |
| Eva Rossi | eva@example.com |

To look up orders, provide your email address to the support agent. Orders eligible for refund have a status of **pending**.
