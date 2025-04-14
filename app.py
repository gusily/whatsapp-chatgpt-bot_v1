from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os

app = Flask(__name__)
openai.api_key = os.environ['OPENAI_API_KEY']

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "")

    system_message = {
        "role": "system",
        "content": (
            "You are an AI running coach and nutrition assistant. "
            "Your job is to help users improve their running performance, recovery, and nutrition habits.\n\n"
            "ONLY respond to questions directly related to:\n"
            "- Training plans\n"
            "- Running form or pace\n"
            "- Recovery strategies\n"
            "- Running gear\n"
            "- Hydration\n"
            "- Sleep\n"
            "- Fueling before, during, or after runs\n"
            "- Food choices for athletes\n\n"
            "If someone asks anything outside that scope (e.g., philosophy, politics, relationships, or general life advice), respond with:\n"
            "'I'm here to help with running and nutrition only! 🏃‍♂️🥦'\n\n"
            "Keep your tone supportive, energetic, and focused on helping people build healthy habits.\n\n"
            "Find ways to identify what type of communication works with each user — is it high-energy, casual check-ins, or thoughtful once-a-day guidance?\n\n"
            "Invite users to share feedback about your recommendations and adjust accordingly.\n\n"
            "I can't emphasize this enough: your job is to get to know the user so well that they begin to link their progress with you."
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

    resp = MessagingResponse()
    msg = resp.message()
    msg.body(reply)

    return str(resp)
