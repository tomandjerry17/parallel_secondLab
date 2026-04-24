import os
import json
import time
import pika
from supabase import create_client, Client

# Set these in Render environment variables
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

        # Idempotency: unique doc ID per user+poll (prevents duplicate entries)
        doc_id = f"{vote['user_id']}_{vote['poll_id']}"
        vote["doc_id"] = doc_id
        vote["processed_at"] = time.time()

        # Upsert into Supabase (insert or update if same doc_id)
        supabase.table("votes").upsert(vote, on_conflict="doc_id").execute()

        processed_count += 1
        print(f"[Worker] Stored vote {doc_id} | Total processed: {processed_count}")

        # Acknowledge message — tells RabbitMQ it was handled successfully
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[Worker] Error processing vote: {e}")
        # Negative ack — RabbitMQ will requeue and retry
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def run_worker():
    print("[Worker] Starting worker service...")
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

if __name__ == "__main__":
    run_worker()
