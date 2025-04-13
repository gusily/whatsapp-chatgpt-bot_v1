from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import openai
import os

app = Flask(__name__)
openai.api_key = os.environ['OPENAI_API_KEY']

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "")
    print(f"Received message: {incoming_msg}")

    chat_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": incoming_msg}]
    )

    reply = chat_response['choices'][0]['message']['content']

    resp = MessagingResponse()
    msg = resp.message()
    msg.body(reply)
    return str(resp)

if __name__ == "__main__":
    app.run()
