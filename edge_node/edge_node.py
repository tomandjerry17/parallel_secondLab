import uuid
import random
import time
import requests
import os

# Replace with your actual Render API URL after deployment
API_URL = os.getenv("API_URL", "http://localhost:5000/vote")
NODE_ID = os.getenv("NODE_ID", f"node-{uuid.uuid4().hex[:6]}")

vote_count = 0

def generate_vote():
    return {
        "user_id": str(uuid.uuid4()),
        "poll_id": "poll_1",
        "choice": random.choice(["A", "B", "C"]),
        "timestamp": time.time(),
        "edge_id": NODE_ID
    }

def send_vote(vote, retries=3):
    for attempt in range(retries):
        try:
            response = requests.post(API_URL, json=vote, timeout=5)
            if response.status_code == 200:
                print(f"[{NODE_ID}] Vote sent: {vote['user_id']} | Choice: {vote['choice']}")
                return True
            else:
                print(f"[{NODE_ID}] Server error {response.status_code}, retrying...")
        except Exception as e:
            print(f"[{NODE_ID}] Transmission failed (attempt {attempt+1}): {e}")
            time.sleep(1)
    print(f"[{NODE_ID}] Failed to send vote after {retries} attempts.")
    return False

def run_edge_node(duplicate=False):
    global vote_count
    print(f"[{NODE_ID}] Edge node started.")
    while True:
        vote = generate_vote()
        send_vote(vote)
        vote_count += 1

        # Fault injection: send duplicate (for Part 5 testing)
        if duplicate:
            print(f"[{NODE_ID}] Sending intentional duplicate...")
            send_vote(vote)

        print(f"[{NODE_ID}] Total votes sent: {vote_count}")
        time.sleep(random.uniform(1, 3))

if __name__ == "__main__":
    # Set duplicate=True when doing fault injection testing (Part 5 Step 1)
    run_edge_node(duplicate=False)
