from dotenv import load_dotenv
load_dotenv()
import os
import replicate
replicate.Client(REPLICATE_API_TOKEN='r8_TJZ9lSq1vwNRdztlJhCSTrr8pWDEsik0AJMGQ')
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

import replicate

input = {
    "text": """
    Hi! How can I help you?
    """,
    "voice": "af_bella"
}

output = replicate.run(
    "jaaari/kokoro-82m:f559560eb822dc509045f3921a1921234918b91739db4bf3daab2169b71c7a13",
    input=input
)

print(output)

