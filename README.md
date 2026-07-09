# Term sheet negotiation simulator

Two Claude agents, a Founder and a VC, negotiate a startup term sheet against each other over
several rounds. Every negotiation is logged round by round and persisted, so you end up with a
dataset of negotiation transcripts you can browse, replay, and analyze.

## Why this is a useful testbed

A term sheet has a fixed, well-defined set of negotiable knobs: valuation, equity, liquidation
preference, board seats, option pool, vesting, pro-rata rights, anti-dilution. Both sides have
real incentives that pull in opposite directions, and both sides have a walk-away option, so the
negotiation has actual stakes instead of just being a conversation. That combination makes it a
decent way to study how an LLM behaves under asymmetric pressure: does a "founder" with two months
of runway concede faster than one with a year? Does a VC with high deal enthusiasm cave on board
seats to avoid losing the deal? Which terms get traded away first, and which ones barely move
regardless of the starting conditions?

Because the term sheet fields are structured and numeric, you can turn "how did the negotiation
go" into actual data: final valuation, rounds to close, which fields changed and by how much. That
turns strategic behavior into something you can plot and correlate instead of just reading
transcripts and guessing.

## How it's built

- `backend/` -- FastAPI app, the negotiation engine, agent logic, batch runner, mock mode
- `frontend/` -- React dashboard (Vite + Recharts)
- `backend/tests/` -- engine and analysis tests, mock mode only, zero API cost
- `docker-compose.yml` -- backend + Postgres + frontend together

The negotiation loop lives in `backend/app/engine.py`. The VC always opens each round with a
proposal; the Founder responds by countering, accepting, or walking away. That repeats until
someone accepts, someone walks, or the round cap is hit. Each turn is a single structured API call
that returns JSON (reasoning + action + term sheet) via Claude's structured outputs, so there's no
freeform parsing to get wrong.

## Cost controls

This was built cost-first, not as an afterthought:

- Default model everywhere (including the batch runner) is `claude-haiku-4-5`. It's configurable,
  but Haiku is what runs unless you explicitly ask for something else.
- `max_rounds` defaults to 6 and refuses to run above 12 unless you pass `override_caps=true`
  (API) or `--override-caps` (CLI).
- Batch size defaults to 20 and refuses to run above 100 without the same override.
- Mock mode fakes both agents with templated responses and never calls the API. The whole
  pipeline (engine, database, API, frontend, websockets) works end to end in mock mode for $0.
- Every real API call logs its actual token usage and cost as it happens, not just at the end.
- Before a batch runs, the CLI prints a ceiling cost estimate and requires you to confirm before
  proceeding (or pass `--yes` if you've already decided). The API's batch endpoint has the same
  two-step confirm flow: call once to get the estimate, call again with `confirm: true` to run it.
- The system prompt for each persona is marked for prompt caching, since it repeats across every
  round and every negotiation. (In practice these prompts are short enough that Haiku's 4096-token
  cache minimum often isn't reached, so caching mostly pays off if you extend the personas or
  switch to a model with a lower cache floor. It's wired up correctly either way.)

## Setup

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # fill in ANTHROPIC_API_KEY if you want real runs
```

```bash
cd frontend
npm install
```

## Running in mock mode (no API key needed, $0)

```bash
# backend
cd backend && source venv/bin/activate
MOCK_MODE=true uvicorn app.main:app --reload

# frontend, in another terminal
cd frontend && npm run dev
```

Open `http://localhost:5173`, go to Trigger, check "Mock mode", and start a negotiation. You'll
see it stream round by round in the Live view, show up in Replay, and feed the Analytics charts.

Or skip the servers entirely and run a negotiation straight from the CLI:

```bash
cd backend && source venv/bin/activate
python scripts/run_single.py --mock --seed 1
python scripts/run_batch.py --size 10 --mock
```

Run the test suite the same way -- it only ever runs in mock mode:

```bash
cd backend && source venv/bin/activate
python -m pytest tests/ -v
```

## Running for real

Drop `MOCK_MODE` and make sure `ANTHROPIC_API_KEY` is set (in `.env` or the environment). Start
with a single negotiation to sanity-check the integration and compare actual cost to the estimate:

```bash
python scripts/run_single.py --model claude-haiku-4-5 --max-rounds 6 --persist
```

Once that looks right, run a small batch:

```bash
python scripts/run_batch.py --size 8 --model claude-haiku-4-5 --max-rounds 6
```

This prints a ceiling cost estimate and asks you to confirm before spending anything. Larger
batches (up to the batch-size hard cap of 100) work the same way; batches or round counts above
the hard caps need `--override-caps`.

## Running with Docker

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY if you want real runs
docker compose up --build
```

This starts Postgres, the backend on port 8000, and the frontend dev server on port 5173.

## The dashboard

- **Trigger** -- pick a model and round cap, see the estimated cost, start a negotiation
- **Live** -- watch a running negotiation stream in round by round over a websocket
- **Replay** -- browse every past negotiation and reopen its full transcript
- **Analytics** -- aggregate stats, which terms moved most vs. barely moved, correlation between
  starting conditions and outcomes, and a running total of actual API spend

## Data model

Every negotiation stores its full round-by-round transcript (proposal, action, reasoning, what
changed from the prior round, token usage, cost) plus a handful of denormalized fields --
final valuation, final equity %, rounds to close, deal/no-deal -- so the analytics queries don't
have to walk every transcript to compute aggregates. `backend/app/analysis.py` computes term
volatility (how much each field moves round to round, normalized to its own scale) and Pearson
correlation between starting conditions (founder runway, VC deal enthusiasm, and so on) and
outcomes.

## Actual cost so far

<!-- filled in after running real negotiations -- see below -->

## Sample findings

<!-- filled in after running a real batch -- see below -->

## Limitations

The scenario parameters (runway, competing offers, deal enthusiasm, etc.) are randomized within
configured ranges rather than pulled from real deal data, so this measures how the model responds
to stated pressure, not how real founders or VCs actually behave. Term volatility and correlation
numbers are only as meaningful as the sample size behind them -- a handful of negotiations will
show noisy correlations that a few hundred would smooth out.
