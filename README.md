# Distributed Voting System — CS323 Lab 2
**Stack:** Render (API + Worker) · CloudAMQP RabbitMQ · Supabase  
**Architecture:** `Edge Node → Flask API (Render) → RabbitMQ (CloudAMQP) → Worker (Render) → Supabase`
![Architecture Diagram](voting_system_architecture.svg)

---

## Why this stack instead of GCP?
GCP requires a billing account with a credit card. This stack replicates the **exact same distributed architecture** using free-tier services only — no credit card required:

| GCP (Original) | Our Alternative | Role |
|---|---|---|
| Cloud Run | Render (Web Service) | Hosts API & Worker |
| Pub/Sub | CloudAMQP (RabbitMQ) | Asynchronous message queue |
| Firestore | Supabase (PostgreSQL) | Persistent vote storage |

---

## System Overview

This system simulates a distributed voting pipeline where multiple edge nodes independently generate votes and send them to a cloud API. The API publishes each vote as a message to RabbitMQ, which buffers them asynchronously. A worker service continuously consumes those messages and writes them to Supabase. The system was designed to remain functional even when individual components fail.

**Live API Endpoint:** https://api-ykgx.onrender.com
**Live Worker Endpoint:** https://worker-m5bb.onrender.com

---

## Project Structure
```
voting-system/
├── edge_node/
│   ├── edge_node.py       # Simulates distributed edge clients
│   └── requirements.txt
├── api/
│   ├── app.py             # Flask API — validates and queues votes
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

4. Run this to disable Row Level Security (required for the worker to write data):
```sql
ALTER TABLE votes DISABLE ROW LEVEL SECURITY;
```

5. Go to **Settings → API**
6. Copy your **Project URL** and **anon/public API Key** — you will need these in Step 4

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
2. Push your `api/` folder to a GitHub repository
3. In Render, click **New → Web Service**
4. Connect your GitHub repo and set the **Root Directory** to `api/`
5. Set these:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
6. Add **Environment Variable:**
   - Key: `RABBITMQ_URL` | Value: *(your CloudAMQP AMQP URL)*
7. Click **Deploy** and copy the URL Render gives you (e.g. `https://voting-api-xxxx.onrender.com`)

---

### STEP 4 — Deploy the Worker to Render

> **Note:** Render's Background Worker requires a paid plan. Instead, the worker is deployed as a second **Web Service** — it runs the RabbitMQ consumer loop in a background thread while Flask handles the main thread to satisfy Render's free tier HTTP requirement.

1. In Render, click **New → Web Service**
2. Connect the same GitHub repo and set the **Root Directory** to `worker/`
3. Set these:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn worker:app`
4. Add **Environment Variables:**
   - Key: `RABBITMQ_URL` | Value: *(your CloudAMQP AMQP URL)*
   - Key: `SUPABASE_URL` | Value: *(your Supabase Project URL)*
   - Key: `SUPABASE_KEY` | Value: *(your Supabase anon key)*
5. Click **Deploy**
6. Verify it is running by visiting the worker URL in your browser — it should return `{"status": "worker running", "processed": 0}`

---

### STEP 5 — Run Edge Nodes Locally

Each group member runs this on their own machine. On **Windows PowerShell**, run these one line at a time:

```powershell
$env:API_URL = "https://your-api-url.onrender.com/vote"
$env:NODE_ID = "node-yourname"
python edge_node.py
```

Replace `https://your-api-url.onrender.com` with your actual Render API URL from Step 3, and replace `node-yourname` with each member's own identifier so edge sources can be distinguished in the logs.

---

## Fault Injection Testing (Part 5)

### Step 1 — Simulate Message Duplication

In `edge_node.py`, change the last line to:
```python
run_edge_node(duplicate=True)
```
Run the edge node for about 30 seconds. Each vote is intentionally sent twice to simulate network-induced duplication or retry behavior.

**Observed result:** Despite receiving duplicate messages, Supabase showed each `doc_id` only once. This confirms that idempotency is correctly enforced — duplicate deliveries result in the same final state, not multiple records.

### Step 2 — Simulate Worker Failure

1. In Render, go to your **Worker** web service
2. Click the three-dot menu `⋯` → click **Suspend Service**
3. Run the edge node normally while the worker is suspended
4. Check **CloudAMQP → RabbitMQ Manager → Queues** — the **Ready** count rises as votes pile up

**Observed result:** During worker downtime, the API continued accepting votes normally and RabbitMQ buffered a large number of messages. Supabase received no new rows. Notably, the worker stopped consuming messages even before it was manually suspended — Render's free tier automatically idles Web Services after a period of inactivity, which caused the worker to silently stop processing. This demonstrated an additional real-world failure mode: infrastructure-level timeouts that are invisible at the application layer.

### Step 3 — Restore Worker and Observe Recovery

1. In Render, click **Resume Service** on the Worker
2. Wait 30–60 seconds for the worker to boot up
3. Refresh **Supabase → Table Editor → votes** — rows appear in batches automatically
4. Refresh **CloudAMQP → Queues** — the Ready count drops back to 0

**Observed result:** After resuming the worker service, it did not automatically reconnect and process the queued messages as expected. Supabase remained empty and CloudAMQP messages continued accumulating. A manual redeploy (Clear cache & Deploy) was required to fully restart the worker, after which it successfully reconnected to RabbitMQ, drained all queued messages, and Supabase was fully updated with no data loss.

---

## System Evaluation Summary

| Condition | API | RabbitMQ | Worker | Supabase |
|---|---|---|---|---|
| Normal Operation | ✅ Accepting | ✅ Flowing | ✅ Processing | ✅ Updating |
| Worker Suspended | ✅ Accepting | ✅ Buffering (68 msgs) | ❌ Down | ⏸ Paused |
| After Recovery | ✅ Accepting | ✅ Drained to 0 | ✅ Recovered | ✅ Caught up |

**Key findings:**
- RabbitMQ successfully buffered all votes during worker downtime with zero message loss
- Idempotency via `doc_id` primary key prevented duplicate rows even when votes were sent twice
- The system recovered automatically with no manual replay or intervention required
- Failure was isolated — only the worker was affected, the API and queue remained fully operational

---

## System Architecture Diagram

```
[Edge Node A] ──┐
[Edge Node B] ──┼──► [Flask API on Render] ──► [RabbitMQ on CloudAMQP]
[Edge Node C] ──┘         (validates &                (buffers votes
[Edge Node D] ──┐          publishes)                  asynchronously)
[Edge Node E] ──┘                                            │
                                                             ▼
                                                  [Worker Service on Render]
                                                    (consumes & deduplicates)
                                                             │
                                                             ▼
                                                  [Supabase PostgreSQL]
                                                    (persistent storage)
```

---

## Individual Reflections

### Member 1 — [Bao, Roger Jr E.]
Setting up this distributed system was more frustrating than I expected, especially when it came to connecting the APIs. Getting the environment variables right across Render, CloudAMQP, and Supabase felt like a guessing game at times — one wrong URL or missing key and nothing would work, with error messages that weren't always helpful in pointing out exactly what went wrong. There were moments where the API would accept votes fine but the worker would silently fail to write anything to Supabase, and tracing that back to a misconfigured SUPABASE_KEY took longer than I'd like to admit.
What surprised me most was how the system kept running even when parts of it broke. Watching RabbitMQ hold onto all those messages while the worker was down showed me that good architecture can buy you time to fix problems without losing data. But it also made me appreciate how much invisible work goes into keeping distributed components actually talking to each other — something that's easy to take for granted until an API connection silently drops and you have no idea why.

### Member 2 — [Lagayada, Bea A.]
*In my experience in basic python programming where everything runs line by line and I can predict exactly what happens, this distributed system felt completely different. In a normal script, if I send a vote, I immediately know if it worked or failed, but here I would run my edge node locally, see "vote sent" in my terminal, and then have no clue when the worker would pick it up. Watching RabbitMQ buffer messages while the worker was suspended was stressful but impressive. Messages piled up like a waiting line, and even when Render's free tier silently stopped the worker, not a single vote was lost. The scariest moment was after resuming the worker when nothing happened automatically. I had to manually redeploy to get it reconnected, which taught me that automatic recovery isn't always automatic. The coolest part was edge computing. My laptop was just a dumb sender, talking to a cloud API, then RabbitMQ, then a worker, then Supabase. I could unplug my Wi-Fi mid send, my script would retry, and the cloud side kept working. But it made me wonder: what happens if the API itself goes down? How do real systems handle thousands of edge nodes without RabbitMQ becoming the bottleneck? And with idempotency using a primary key, if two votes arrive at nearly the same time, does the database lock and slow everything down? Building this small system showed me that real world distributed systems are messy, and handling that mess without breaking is the real challenge.*

### Member 3 — [Laplap, Mariel]
*(Write 1–2 paragraphs based on your actual experience. Consider: How did the fault injection tests change your understanding of distributed systems? What was interesting about watching the worker recover automatically? What trade-offs did you notice between simplicity and reliability?)*

### Member 4 — [Martinez, Thomas Gabriel D.]
*For me, the most challenging part of this laboratory activity was setting up the cloud services. Creating accounts and configuring Render, Supabase, and CloudAMQP each had their own steps and settings to get right, and it was not always clear what needed to be done in what order. Unlike writing code where you can test things immediately, setting up cloud infrastructure means waiting for deployments, checking environment variables, and troubleshooting across multiple dashboards at the same time. It took patience to get everything connected properly, and I gained a deeper appreciation for how much work goes into preparing the environment before a distributed system can even run. The most surprising moment for me during the activity was when I found out that the worker service had stopped consuming messages on its own, even before it was intentionally suspended. I expected failures to be obvious, like an error message or a crash, but instead the worker just quietly went idle while everything else kept running. The API was still accepting votes and CloudAMQP was still receiving them, but nothing was reaching Supabase. Seeing that happen made me realize that in distributed systems, components can fail in ways that are completely invisible if you are not actively monitoring them. Running my own edge node and watching my votes appear in Supabase under my node name was a satisfying moment that made the whole system feel real and connected, and it helped me understand how multiple independent sources can contribute to a shared cloud pipeline at the same time.*

### Member 5 — [Ruelo, Cydney]
*The most unexpected outcome of the project came during the worker failure test, when I pulled up the RabbitMQ dashboard on CloudAMQP and watched the Ready count climb steadily to 68 messages. That was when everything finally clicked, seeing the queue silently absorb every incoming vote in real time made message buffering make sense to me in a way that no diagram ever had. It was further surprising that Render's free tier had silently paused my worker before I had done so manually with no error or signal, thereby exhibiting in practice how timeouts at the infrastructure layer could be completely abstracted from the application layer. The test demonstrated to me that eventual consistency functions as a real-world process because the API vote processing showed a normal delay, which disappeared when workers operated correctly but showed a complete database freeze at its latest recorded point because votes kept building up in the queue. The worker's reconnection behavior is the main thing I would change if I were building this for a real election because it is simply unacceptable in a high-stakes situation to have to manually trigger a full redeploy just to resume processing. I would also add an explicit health-check loop, dead-letter queue handling, and ready count threshold alerts so that a worker who is silently stalled could never go unnoticed because in a real voting system, silent failures are not just a reliability problem but also a trust problem.*
