# client.py
import asyncio
import json
import threading
import tkinter as tk
from tkinter import ttk
import websockets
import platform

SERVER_URL = "ws://localhost:8765"

class PresenceClient:
    def __init__(self, root, user_id):
        self.root = root
        self.user_id = user_id
        self.buttons = {}
        self.status_labels = {}
        self.ws = None

        root.title(f"User: {user_id}")
        root.geometry("300x400")

        self.frame = tk.Frame(root)
        self.frame.pack(pady=10)

        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_until_complete, args=(self.run(),), daemon=True).start()

    async def run(self):
        async with websockets.connect(SERVER_URL) as ws:
            self.ws = ws
            await ws.send(self.user_id)  # Send ID

            # Heartbeat task
            asyncio.create_task(self.send_heartbeat())

            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                self.handle_message(data)

    async def send_heartbeat(self):
        while True:
            if self.ws:
                await self.ws.send(json.dumps({"type": "heartbeat"}))
            await asyncio.sleep(30)

    def handle_message(self, data):
        if data["type"] == "status_update":
            uid = data["user"]
            status = data["status"]
            self.update_status(uid, status)

        elif data["type"] == "pulse_click":
            uid = data["from"]
            self.pulse_glow(uid, "yellow")

        elif data["type"] == "double_pulse":
            uid = data["from"]
            self.pulse_glow(uid, "red")

    def update_status(self, uid, status):
        if uid in self.status_labels:
            self.status_labels[uid]["text"] = f"{uid}: {status}"
            self.status_labels[uid]["foreground"] = "green" if status == "online" else "gray"

    def pulse_glow(self, uid, color):
        if uid in self.buttons:
            btn = self.buttons[uid]

            # Use a neutral default that works across themes
            default_color = ttk.Style().lookup("TButton", "background")
            if not default_color:
                default_color = "SystemButtonFace" if platform.system() == "Windows" else "#f0f0f0"

            btn.config(background=color)
            self.root.after(300, lambda: btn.config(background=default_color))


    def add_linked_user(self, uid):
        label = tk.Label(self.frame, text=f"{uid}: offline", foreground="gray")
        label.pack()
        self.status_labels[uid] = label

        btn = tk.Button(self.frame, text=f"Pulse {uid}", command=lambda: self.send_pulse(uid))
        btn.pack(pady=5)
        self.buttons[uid] = btn

    def send_pulse(self, uid):
        if self.ws:
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({"type": "pulse_click", "target": uid})),
                self.loop
            )


def start_client(user_id, linked_users):
    root = tk.Tk()
    client = PresenceClient(root, user_id)
    for uid in linked_users:
        client.add_linked_user(uid)
    root.mainloop()


if __name__ == "__main__":
    # Example: run `python client.py user1 user2 user3`
    import sys
    uid = sys.argv[1]
    links = sys.argv[2:]
    start_client(uid, links)
