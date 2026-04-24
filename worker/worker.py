import os
import json
import time
import threading
import pika
from flask import Flask, jsonify
from supabase import create_client, Client

app = Flask(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
QUEUE_NAME = "vote-queue"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
processed_count = 0

def process_vote(ch, method, properties, body):
    global processed_count
    try:
        vote = json.loads(body.decode("utf-8"))
        print(f"[Worker] Received vote: {vote['user_id']} | Poll: {vote['poll_id']}")

        doc_id = f"{vote['user_id']}_{vote['poll_id']}"
        vote["doc_id"] = doc_id
        vote["processed_at"] = time.time()

        supabase.table("votes").upsert(vote, on_conflict="doc_id").execute()

        processed_count += 1
        print(f"[Worker] Stored {doc_id} | Total processed: {processed_count}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[Worker] Error: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def run_worker_loop():
    """Runs in a background thread — keeps consuming from RabbitMQ."""
    print("[Worker] Background thread started.")
    while True:
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_vote)
            print("[Worker] Listening for messages...")
            channel.start_consuming()
        except Exception as e:
            print(f"[Worker] Connection lost: {e}. Reconnecting in 5s...")
            time.sleep(5)

# Health check endpoint — required so Render keeps the web service alive
@app.route("/")
def health():
    return jsonify({"status": "worker running", "processed": processed_count}), 200

# Start the worker loop in a background thread when the app boots
worker_thread = threading.Thread(target=run_worker_loop, daemon=True)
worker_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
