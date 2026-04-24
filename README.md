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

The `start.sh` script handles the full setup:

```bash
#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt --quiet

# Seed the database if it doesn't exist
if [ ! -f "bookly.db" ]; then
  echo "Seeding database..."
  python3 -m app.seed
fi

# Start the server
echo "Starting Bookly Support Agent at http://localhost:8000"
python3 -m uvicorn app.main:app --reload
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
