import os
import json
import pika
from flask import Flask, request, jsonify

app = Flask(__name__)

# CloudAMQP connection URL — set this in Render's environment variables
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
QUEUE_NAME = "vote-queue"

def get_channel():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    return connection, channel

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "API is running"}), 200

@app.route("/vote", methods=["POST"])
def receive_vote():
    vote = request.get_json()

    # Validate required fields
    if not vote:
        return jsonify({"error": "Invalid payload"}), 400
    if not all(k in vote for k in ["user_id", "poll_id", "choice"]):
        return jsonify({"error": "Missing fields: user_id, poll_id, or choice"}), 400

    try:
        connection, channel = get_channel()
        message = json.dumps(vote)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=message,
            properties=pika.BasicProperties(delivery_mode=2)  # persistent message
        )
        connection.close()
        print(f"[API] Published vote: {vote['user_id']} | Choice: {vote['choice']}")
        return jsonify({"status": "accepted"}), 200
    except Exception as e:
        print(f"[API] Failed to publish: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
