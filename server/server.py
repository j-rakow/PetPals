# server.py
import asyncio
import json
import time
import websockets
import os

connected_users = {}   # user_id -> websocket
last_heartbeat = {}    # user_id -> timestamp
links = {
    "user1": ["user2", "user3"],
    "user2": ["user1"],
    "user3": ["user1"],
    "user4": ["user5"],
    "user5": ["user4"]
}
last_click_time = {}   # (user, target) -> timestamp
DOUBLE_CLICK_WINDOW = 0.3  # seconds


async def notify_status(user, status):
    """Send online/offline status to all linked users."""
    for partner in links.get(user, []):
        if partner in connected_users:
            await connected_users[partner].send(json.dumps({
                "type": "status_update",
                "user": user,
                "status": status
            }))


async def handler(ws):
    # First message must be user_id
    user_id = await ws.recv()
    connected_users[user_id] = ws
    # Send the online/offline status of all linked users to this client
    for partner in links.get(user_id, []):
        status = "online" if partner in connected_users else "offline"
        await ws.send(json.dumps({
            "type": "status_update",
            "user": partner,
            "status": status
        }))
    last_heartbeat[user_id] = time.time()
    print(f"{user_id} connected")

    # Notify linked users you're online
    await notify_status(user_id, "online")

    try:
        async for message in ws:
            data = json.loads(message)

            if data["type"] == "heartbeat":
                last_heartbeat[user_id] = time.time()

            elif data["type"] == "pulse_click":
                target = data["target"]
                now = time.time()
                last_click_time[(user_id, target)] = now

                # Check double click
                if (target, user_id) in last_click_time and \
                   now - last_click_time[(target, user_id)] <= DOUBLE_CLICK_WINDOW:
                    # Double pulse!
                    for uid in (user_id, target):
                        if uid in connected_users:
                            await connected_users[uid].send(json.dumps({
                                "type": "double_pulse",
                                "from": user_id if uid == target else target
                            }))
                else:
                    # Single pulse
                    if target in connected_users:
                        await connected_users[target].send(json.dumps({
                            "type": "pulse_click",
                            "from": user_id
                        }))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_users.pop(user_id, None)
        print(f"{user_id} disconnected")
        await notify_status(user_id, "offline")


async def heartbeat_checker():
    """Check if clients are still alive."""
    while True:
        now = time.time()
        for user in list(connected_users):
            if now - last_heartbeat.get(user, 0) > 60:
                # Timeout
                connected_users.pop(user, None)
                print(f"{user} timed out")
                await notify_status(user, "offline")
        await asyncio.sleep(5)


async def main():
    port = int(os.environ.get("PORT", 8765))
    server = await websockets.serve(handler, "0.0.0.0", port)
    print("Server running on ws://localhost:8765")
    await asyncio.gather(server.wait_closed(), heartbeat_checker())


if __name__ == "__main__":
    asyncio.run(main())
