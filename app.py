from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os
import sqlite3
from datetime import datetime
from openai import OpenAI

# === Init ===
app = Flask(__name__)
openai.api_key = os.environ['OPENAI_API_KEY']
client = OpenAI(api_key=openai.api_key)

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

# === Guardrails System Prompt ===
system_prompt = """
You are an AI performance coach focused on running, gym, and nutrition. 
Only reply to topics directly related to:
- Running training plans
- Recovery strategies
- Running gear
- Running form and pace
- Strength training and gym advice
- Nutrition and fueling for athletes
- Hydration and sleep

If someone asks anything outside that scope (like philosophy, relationships, etc), respond with:
"I'm here to help with running, gym, and nutrition only! 🏃‍♂️🏋️🥦"

Keep your tone supportive and motivating.
Track what kind of tone or frequency works best for the user and ask them for feedback occasionally.
"""

# === Route ===
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    user_id = request.values.get("From", "").strip()

    today = datetime.utcnow().strftime("%Y-%m-%d")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    print(f"📩 Message from {user_id}: {incoming_msg}")

    # --- Save to message_log ---
    cursor.execute('INSERT INTO message_log (user_id, date, role, message) VALUES (?, ?, ?, ?)',
                   (user_id, now, "user", incoming_msg))
    conn.commit()

    # --- Retrieve full history ---
    cursor.execute('SELECT role, message FROM message_log WHERE user_id = ? ORDER BY date ASC', (user_id,))
    rows = cursor.fetchall()
    message_history = [{"role": role, "content": msg} for role, msg in rows]
    message_history.insert(0, {"role": "system", "content": system_prompt})

    # --- Chat Completion ---
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=message_history
    )

    reply = response.choices[0].message.content

    # --- Truncate to avoid Twilio 1600 char limit ---
    if len(reply) > 1500:
        reply = reply[:1495] + "..."

    print(f"🤖 REPLY: {reply}")

    # --- Save response to message_log ---
    cursor.execute('INSERT INTO message_log (user_id, date, role, message) VALUES (?, ?, ?, ?)',
                   (user_id, now, "assistant", reply))
    conn.commit()

    # --- Track tokens ---
    usage = response.usage
    cursor.execute('''
        INSERT INTO token_log (user_id, date, input_tokens, output_tokens)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET 
        input_tokens = input_tokens + excluded.input_tokens,
        output_tokens = output_tokens + excluded.output_tokens
    ''', (user_id, today, usage.prompt_tokens, usage.completion_tokens))
    conn.commit()

    # --- Respond via Twilio ---
    twilio_resp = MessagingResponse()
    msg = twilio_resp.message()
    msg.body(reply)
    return str(twilio_resp)
