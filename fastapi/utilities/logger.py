import httpx
from fastapi import BackgroundTasks, Request

# Your Discord webhook URL goes here
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1216247078544740432/qaeahy5_b1m-4I-0vhzl-gJYMrr8Py0f4FtvIwo3wedlhzTf8BS_zWa-3teSUbjafCxm'

# Async function to send log messages to Discord
async def send_log_to_discord(message: str):
    async with httpx.AsyncClient() as client:
        data = {"content": message}
        await client.post(DISCORD_WEBHOOK_URL, json=data)

# Function to add a task to log to Discord in the background
def log_to_discord(background_tasks: BackgroundTasks, message: str):
    background_tasks.add_task(send_log_to_discord, message)

# Helper function to construct and send the log message including the client's IP
def log_user_activity(request: Request, background_tasks: BackgroundTasks, username: str, action: str):
    client_ip = request.client.host
    log_message = f"{username} has {action}. IP: {client_ip}"
    log_to_discord(background_tasks, log_message)

    