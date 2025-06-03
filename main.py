import json
from datetime import datetime
# from openai import AsyncOpenAI
from dotenv import load_dotenv
from openai import OpenAI
from typing import Final
from telegram import Update
from telegram.ext import ApplicationBuilder, Application, CommandHandler, MessageHandler, filters, ContextTypes
import os
import asyncio

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN: Final = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY: Final = os.getenv("OPENAI_API_KEY")
BOT_USERNAME: Final = "@rrunning_coach_bot"
# BOT_USERNAME: Final = os.getenv("BOT_USERNAME", "@rrunning_coach_bot")

# Validate keys exist
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in environment variables")
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in environment variables")


client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


MEMORY_FILE = "user_data.json"


def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                # File is empty
                return {}
            return json.loads(content)
    except FileNotFoundError:
        # File doesn't exist
        return {}
    except json.JSONDecodeError as e:
        # File contains invalid JSON
        print(f"Error loading memory file: {e}")
        print("Creating new empty memory")
        return {}


def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


# --------- CHATGPT UTILITIES ---------
def classify_and_extract(user_message):
    today_str = datetime.now().strftime("%Y-%m-%d")

    response = client.responses.create(
        model="gpt-4o",  # "gpt-4.1-nano"
        instructions=f"""
        You are a helpful assistant for a running coach bot.

        If the user is logging a run, extract the date (or assume that the date is today), activity, and distance (in km). Set intent to "log_run".
        I want the date in YYYY-MM-DD format. For reference, today is: {today_str}
        If the user is asking for progress analysis, set intent to "analyze_progress".
        Otherwise, set intent to "unknown".

        Respond in this JSON format:
        {{
        "intent": ...,
        "activity": ...,
        "distance_km": ...,
        "date": ...,
        "request_language": ...
        }}
        If fields are not relevant, use null.
        """,
        input=user_message,
    )

    raw_output = response.output_text
    json_start = raw_output.find("{")
    json_end = raw_output.rfind("}")
    json_str = raw_output[json_start:json_end+1]
    data = json.loads(json_str)

    return data
    
    # return {"intent": "log_run", "activity": "running", "distance_km": "5", "date": "2023-09-01", "request_language": "en"}


# commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Hello {update.effective_user.first_name}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Type the distance of your run in kilometers")


async def custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("This is a custom command")


# # responses
# def handle_response(text: str) -> str:
#     processed: str = text.lower()

#     if "hello" in processed:
#         return "Hey there!"

#     if "how are you" in processed:
#         return "I am fine"

#     if "won-won" in processed:
#         return "STOP!"

#     return "I am sorry, I do not understand your question"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    message_type: str = update.message.chat.type
    message: str = update.message.text

    if message_type == "group":
        if BOT_USERNAME in message:
            message: str = message.replace(BOT_USERNAME, "").strip()
        else:
            return

    print(f"User ({update.message.chat.id}) in {message_type}: {message}")

    memory = load_memory()
    user_memory = memory.get(user_id, [])

    result = classify_and_extract(message)

    if result["intent"] == "log_run":
        date = result["date"]
        entry = {
            "date": date,
            "distance_km": result["distance_km"]
        }
        user_memory.append(entry)
        memory[user_id] = user_memory
        save_memory(memory)

        print("Memory:")
        print(memory)
        print()

        await update.message.reply_text(f"Logged: {entry['distance_km']} km run on {entry['date']}.")        
    elif result["intent"] == "analyze_progress":
        response = "I beg your pardon?"
        print(f"User ({update.message.chat.id}) in {message_type}: {message}")
        print(result)
        print(f"Bot ({BOT_USERNAME}): {response}")
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("Sorry, I didn’t understand that. Try logging a run or asking about your progress.")


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")


async def main():
    print("Bot started...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Delete any existing webhooks before starting polling
    print("Clearing webhooks...")
    await app.bot.delete_webhook(drop_pending_updates=True)
    print("Webhooks cleared!")

    # commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("custom", custom_command))

    # messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # errors
    app.add_error_handler(error)

    await app.initialize()
    await app.start()

    # poll
    print("Polling...")
    await app.updater.start_polling(poll_interval=3)
    # app.run_polling(poll_interval=3)

    # Keep the bot running
    try:
        # Wait forever
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nStopping bot...")
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
