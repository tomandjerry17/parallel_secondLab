# Distributed Voting System — CS323 Lab 2
**Stack:** Render (API + Worker) · CloudAMQP RabbitMQ · Supabase  
**Architecture:** `Edge Node → Flask API (Render) → RabbitMQ (CloudAMQP) → Worker (Render) → Supabase`

---

## Why this stack instead of GCP?
GCP requires a billing account with a credit card. This stack replicates the **exact same distributed architecture** using free-tier services only:

| GCP (Original) | Our Alternative | Role |
|---|---|---|
| Cloud Run | Render | Hosts API & Worker |
| Pub/Sub | CloudAMQP (RabbitMQ) | Message queue |
| Firestore | Supabase | Database |

---

## Project Structure
```
voting-system/
├── edge_node/
│   ├── edge_node.py       # Simulates distributed edge clients
│   └── requirements.txt
├── api/
│   ├── app.py             # Flask API — receives and queues votes
│   └── requirements.txt
└── worker/
    ├── worker.py          # Consumes queue and stores to Supabase
    └── requirements.txt
```

---

## Step-by-Step Setup

### STEP 1 — Supabase (Database)

1. Go to https://supabase.com and sign up (free, no credit card)
2. Click **New Project**, name it `voting-system`
3. After it loads, go to **SQL Editor** and run this query to create your table:

```sql
CREATE TABLE votes (
  doc_id TEXT PRIMARY KEY,
  user_id TEXT,
  poll_id TEXT,
  choice TEXT,
  timestamp FLOAT,
  edge_id TEXT,
  processed_at FLOAT
);
```

4. Go to **Settings → API**
5. Copy your **Project URL** and **anon/public API Key** — you'll need these later

---

### STEP 2 — CloudAMQP (Message Queue)

1. Go to https://www.cloudamqp.com and sign up (free, no credit card)
2. Click **Create New Instance**
3. Name it `vote-queue`, select the **Little Lemur (Free)** plan
4. Choose region **US-East-1** (or closest to you)
5. After creation, click your instance and copy the **AMQP URL**
   - It looks like: `amqps://user:password@hostname/vhost`

---

### STEP 3 — Deploy the API to Render

1. Go to https://render.com and sign up (free, no credit card)
2. Push your `api/` folder to a GitHub repo (create one if needed)
3. In Render, click **New → Web Service**
4. Connect your GitHub repo, select the `api/` folder as root
5. Set these:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
6. Add **Environment Variable:**
   - Key: `RABBITMQ_URL` | Value: *(your CloudAMQP AMQP URL)*
7. Click **Deploy** — copy the URL it gives you (e.g. `https://voting-api-xxxx.onrender.com`)

---

### STEP 4 — Deploy the Worker to Render

1. In Render, click **New → Web Service (same type as the API)**
2. Connect the same GitHub repo, select the `worker/` folder as root
3. Set these:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn worker:app`
4. Add **Environment Variables:**
   - Key: `RABBITMQ_URL` | Value: *(your CloudAMQP AMQP URL)*
   - Key: `SUPABASE_URL` | Value: *(your Supabase Project URL)*
   - Key: `SUPABASE_KEY` | Value: *(your Supabase anon key)*
5. Click **Deploy**

---

### STEP 5 — Run Edge Nodes Locally

Each group member runs this on their own machine:

```bash
cd edge_node
pip install -r requirements.txt
API_URL=https://your-api-url.onrender.com/vote python edge_node.py
```

Replace `https://your-api-url.onrender.com` with the Render URL from Step 3.

Each group member sets a different `NODE_ID` to distinguish sources:
```bash
API_URL=https://your-api.onrender.com/vote NODE_ID=node-alice python edge_node.py
```

---

## Fault Injection Testing (Part 5)

### Simulate Message Duplication (Step 1)
In `edge_node.py`, change the last line to:
```python
run_edge_node(duplicate=True)
```
Watch Supabase — duplicate votes should NOT create duplicate rows (idempotency via `doc_id` primary key).

### Simulate Worker Failure (Step 2)
1. In Render, go to your **Worker service**
2. Click **Suspend Service** (this stops the worker)
3. Keep edge nodes running — votes will pile up in RabbitMQ queue
4. Check CloudAMQP dashboard → you'll see **queued messages accumulating**
5. Supabase will stop receiving new rows

### Restore Worker (Step 3)
1. In Render, **Resume** the worker service
2. Worker reconnects to RabbitMQ automatically
3. All queued messages are processed in batches
4. Supabase catches up — no votes lost

---

## Verifying the System

After running edge nodes for a few minutes, go to Supabase → **Table Editor → votes**. You should see rows appearing with user IDs, choices, and timestamps.

Check CloudAMQP dashboard for:
- Messages published (from API)
- Messages acknowledged (by worker)
- Messages queued (buffered during worker downtime)

---

## System Architecture Diagram

```
[Edge Node A] ──┐
[Edge Node B] ──┼──► [Flask API on Render] ──► [RabbitMQ on CloudAMQP]
[Edge Node C] ──┘                                        │
                                                         ▼
                                              [Worker Service on Render]
                                                         │
                                                         ▼
                                                [Supabase PostgreSQL]
```

---

## Individual Reflections

*(Each group member writes their own paragraph below)*

### Member 1 — [Name]
...

### Member 2 — [Name]
...

### Member 3 — [Name]
...
