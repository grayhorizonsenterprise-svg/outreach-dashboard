"""
Desktop Bridge — control your PC from Telegram.
Send any message to @WorkflowBridgeBot and it runs here.
"""

import subprocess
import requests
import time
import os

TOKEN = "8510103743:AAE6AB7fbTro_CNiiRHpgKhdR8StsaC3f8g"
CHAT_ID = 8083986395
API = f"https://api.telegram.org/bot{TOKEN}"
OFFSET_FILE = os.path.join(os.path.dirname(__file__), ".offset")

ALLOWED_PREFIXES = [
    "run ",      # run a shell command: "run dir C:\\"
    "claude ",   # ask Claude Code: "claude what files are in my project?"
    "open ",     # open a file/app: "open notepad"
    "status",    # get system status
    "help",      # show available commands
]


def send(text):
    requests.post(f"{API}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })


def get_updates(offset):
    try:
        r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
        return r.json().get("result", [])
    except Exception:
        return []


def load_offset():
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            return int(f.read().strip())
    return 0


def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))


def handle(text):
    text = text.strip()
    lower = text.lower()

    if lower == "help":
        return (
            "*Desktop Bridge Commands:*\n"
            "`run <command>` — run a shell command\n"
            "`claude <prompt>` — ask Claude Code\n"
            "`open <app>` — open an app or file\n"
            "`status` — show PC status"
        )

    if lower == "status":
        result = subprocess.run(
            "tasklist | findstr /i python && echo --- && wmic os get FreePhysicalMemory",
            shell=True, capture_output=True, text=True, timeout=10
        )
        return f"```\n{result.stdout[:1500]}\n```"

    if lower.startswith("run "):
        cmd = text[4:]
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output = (result.stdout + result.stderr).strip()
            return f"```\n{output[:3000] or '(no output)'}\n```"
        except subprocess.TimeoutExpired:
            return "Command timed out (30s limit)."
        except Exception as e:
            return f"Error: {e}"

    if lower.startswith("open "):
        target = text[5:]
        try:
            os.startfile(target)
            return f"Opened: {target}"
        except Exception as e:
            return f"Could not open: {e}"

    if lower.startswith("claude "):
        prompt = text[7:]
        try:
            result = subprocess.run(
                ["claude", "-p", prompt, "--no-conversation"],
                capture_output=True, text=True, timeout=120,
                cwd="c:/Users/curti/Downloads/First Agentic Workflows"
            )
            output = (result.stdout + result.stderr).strip()
            return output[:4000] or "(no response)"
        except subprocess.TimeoutExpired:
            return "Claude timed out (120s)."
        except FileNotFoundError:
            return "Claude CLI not found. Make sure `claude` is in your PATH."
        except Exception as e:
            return f"Error: {e}"

    return (
        "Unknown command. Send `help` to see what I can do.\n\n"
        "Quick examples:\n"
        "`run dir C:\\Users\\curti\\Downloads`\n"
        "`claude list my recent prospects`\n"
        "`open notepad`"
    )


def main():
    send("Desktop Bridge is online. Send `help` to see commands.")
    offset = load_offset()

    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1
            save_offset(offset)

            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text", "").strip()

            if chat_id != CHAT_ID:
                continue  # ignore anyone else messaging the bot

            if not text:
                continue

            print(f"[{time.strftime('%H:%M:%S')}] << {text}")
            reply = handle(text)
            send(reply)
            print(f"[{time.strftime('%H:%M:%S')}] >> sent")

        time.sleep(1)


if __name__ == "__main__":
    main()
