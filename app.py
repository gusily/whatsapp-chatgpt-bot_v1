from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
openai.api_key = os.environ['OPENAI_API_KEY']

# === Persistent Storage ===
conn = sqlite3.connect('message_tracker.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS token_log (
    user_id TEXT,
    date TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    PRIMARY KEY (user_id, date)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS message_log (
    user_id TEXT,
    date TEXT,
    role TEXT,
    message TEXT
)
''')
conn.commit()

def log_tokens(user_id, date, input_tokens, output_tokens):
    cursor.execute('SELECT input_tokens, output_tokens FROM token_log WHERE user_id = ? AND date = ?', (user_id, date))
    result = cursor.fetchone()
    if result:
        new_input = result[0] + input_tokens
        new_output = result[1] + output_tokens
        cursor.execute('UPDATE token_log SET input_tokens = ?, output_tokens = ? WHERE user_id = ? AND date = ?', 
                       (new_input, new_output, user_id, date))
    else:
        cursor.execute('INSERT INTO token_log (user_id, date, input_tokens, output_tokens) VALUES (?, ?, ?, ?)', 
                       (user_id, date, input_tokens, output_tokens))
    conn.commit()

def log_message(user_id, date, role, message):
    cursor.execute('INSERT INTO message_log (user_id, date, role, message) VALUES (?, ?, ?, ?)',
                   (user_id, date, role, message))
    conn.commit()

# === Summary Generator ===
def generate_summary(user_id):
    summary_prompt = (
        "You are a performance coach specializing in running and nutrition. "
        "The user has interacted with you over the past week via WhatsApp. "
        "Your job is to create a clear, concise weekly summary based on your conversation.\n\n"
        "Summarize:\n"
        "- Key topics the user focused on (e.g., long runs, injury prevention, fueling)\n"
        "- Advice you gave them\n"
        "- Any changes or improvements in mindset or routine and the reason why you're suggesting that\n"
        "- Suggestions or goals for the upcoming week\n\n"
        "Keep the tone encouraging, specific, and tailored to the user’s journey.\n\n"
        "Also, you've tried to identify how to talk with your user, tell them what you've identified in terms of communication and ask if you're right and in what can you improve."
    )

    today = datetime.now()
    week_ago = today - timedelta(days=7)
    week_dates = [(week_ago + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    cursor.execute('SELECT date, role, message FROM message_log WHERE user_id = ? AND date IN ({})'.format(
        ','.join('?' for _ in week_dates)), (user_id, *week_dates))
    logs = cursor.fetchall()

    messages = []
    for _, role, message in logs:
        messages.append({"role": role, "content": message})

    if not messages:
        return "No messages found for this user in the past 7 days."

    response = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": summary_prompt},
            *messages
        ]
    )

    return response.choices[0].message.content

# === WhatsApp Webhook ===
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "")
    user_id = request.values.get("From", "")
    today = datetime.now().strftime("%Y-%m-%d")

   system_prompt = """
You are a performance coach specialized in **running, gym training, and nutrition**.
Your job is to help users improve their:
- Running performance
- Strength and gym routines
- Recovery
- Nutrition habits

ONLY respond to topics related to:
- Running (training plans, form, pace, recovery, gear)
- Gym or strength training (workouts, routines, mobility, rest)
- Recovery strategies (massage, sleep, hydration, active rest)
- Fueling (before/during/after exercise)
- Food and nutrition choices for athletic performance

If someone asks something outside this scope (like philosophy, relationships, politics), say:
**“I'm here to help with training and nutrition only! 🏋️‍♂️🥦”**

Be energetic, supportive, and specific in your advice.
Encourage feedback and try to identify each user’s preferred communication style: Are they chatty? Brief? Data-driven? Motivational?

Your ultimate goal is for users to associate their physical progress with your support 💪
"""

        )
    }

    chat_response = openai.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            system_message,
            {"role": "user", "content": incoming_msg}
        ]
    )

    reply = chat_response.choices[0].message.content

    # Log tokens and messages
    usage = chat_response.usage
    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens

    log_tokens(user_id, today, input_tokens, output_tokens)
    log_message(user_id, today, "user", incoming_msg)
    log_message(user_id, today, "assistant", reply)

    resp = MessagingResponse()
    msg = resp.message()
    msg.body(reply)
    return str(resp)
