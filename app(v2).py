from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
load_dotenv()
import json
import os
import tempfile
import requests

from exa_py import Exa
exa_api = os.getenv("EXA_API_KEY")
exa = Exa(api_key = exa_api)

from openai import OpenAI
client = OpenAI(
    base_url = "https://api.exa.ai",
    api_key = exa_api,
)

from pinecone import Pinecone
pine_api = os.getenv("PINECONE_API_KEY")
pc = Pinecone(api_key=pine_api)
index = pc.Index(host="avenchatbot-rz0q9xs.svc.aped-4627-b74a.pinecone.io")

import replicate
replicate.Client(REPLICATE_API_KEY='r8_TJZ9lSq1vwNRdztlJhCSTrr8pWDEsik0AJMGQ')
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

def web_search(prompt):
    taskStub = exa.research.create_task(
    instructions = prompt,
    model = "exa-research",
    output_infer_schema = True
    )
    task = exa.research.poll_task(taskStub.id)
    completion = client.chat.completions.create(
        model = "exa-research",
        messages = [
            {"role": "user", "content": prompt}
        ],
        stream = True,
    )
    x = ""
    for chunk in completion:
        if chunk.choices and chunk.choices[0].delta.content:
            x+=str(chunk.choices[0].delta.content)
    return x

class TextModel:
    def __init__(self, model_name, system_prompt):
        self.model_name = model_name
        self.system_prompt = system_prompt
    
    def gen(self, prompt):
        input = {
            "prompt": prompt,
            "system_prompt": self.system_prompt,
        }
        x = ""
        for event in replicate.stream(
            self.model_name,
            input=input
        ):
            x += str(event)
        x = x.replace('\\', '\\\\')
        return x


Assistant = TextModel(
    "openai/o4-mini",
    """
    Context: You are the chat assitant employed by Aven, a finance company.
    Provided the conversation & available knowledge, you are to respond with three kinds of json outputs.
    Case 1: No additional knowledge is needed to answer query. return {"type": "answer", "content": your response}.
    Case 2: Additional knowledge is needed, which maybe available in VectorDB containing Aven Docs. return {"type": "vector", "content": command to search the VectorDB with}.
    Case 3: Additional knowledge is needed, Vector Knowledge is not sufficient, Web Search required. return {"type": "web", "content": command to search the web with}.
    If all knowledge does not suffice, respond appropriately.
    Keep responses short, crisp, polite unless demanded otherwise.
    Note: "Aven" might be misspelled as "Even", "Avian" etc. Autocorrect.
    """
)
class STTModel:
    def __init__(self):
        self.model_name = "openai/gpt-4o-mini-transcribe"
    def run(self, audio_file):
        output = replicate.run(
            self.model_name,
            input={
                #"task": "transcribe",
                "audio_file": audio_file,
                "language": "en",
                #"timestamp": "chunk",
                #"batch_size": 64,
                #"diarise_audio": False,
                "temparature": 0
            }
        )
        x = " ".join(output)
        return x
    
stt = STTModel()

app = Flask(__name__, template_folder=".", static_folder="static")
app.secret_key = "aven01"


@app.route("/", methods=["GET","POST"])
def home():
    return render_template("chatbot.html")


@app.route("/respond", methods=["GET", "POST"])
def respond():
    data = request.get_json()
    convo = f"Conversation: {data['messages']}"
    print("CONVO ", convo)
    response = Assistant.gen(convo)
    print(response)
    response = json.loads(response)
    print(response["type"])
    if response["type"] == "answer":
        return jsonify({'success':True, "message": response["content"]})
    elif response["type"] == "vector":
        vknowledge = ""
        search = index.search(
            namespace = "default",
            query = {
                "inputs": {"text": response["content"]},
                "top_k": 4
            },
            fields = ["category", "chunk_text"],
            rerank = {
                "model": "bge-reranker-v2-m3",
                "top_n": 4,
                "rank_fields": ["chunk_text"] 
            }
        )
        print("SEARCH RESULT ", search)
        n = len(search['result']['hits'])
        vknowledge = [
            search['result']['hits'][i]['fields']['chunk_text'] for i in range(n) if search['result']['hits'][i]['_score'] > 0.6
        ]
        prompt = f"""
        A response to the following conversation is to be provided given the knowledge.

        ### Message History
        {data}

        ### Vector Knowledge
        {vknowledge}
        """
        response = Assistant.gen(prompt)
        print(response)
        response = json.loads(response)
        print(response["type"])
        if response["type"] == "answer":
            return jsonify({'success':True, "message": response["content"]})
        elif response["type"] == "web":
            wknowledge = ""
            info = web_search(response["content"])
            index.upsert_records(
                "default",
                [
                    {
                        "_id": search['question'],
                        'chunk_text': info,
                        "category": "FAQ"
                    }
                ]
            )
            prompt = f"""
            A response to the following conversation is to be provided given the knowledge.

            ### Message History
            {data}

            ### Vector Knowledge
            {vknowledge}

            ### Web Knowledge
            {wknowledge}
            """
            response = Assistant.gen(prompt)
            print(response)
            response = json.loads(response)
            print(response["type"])
            return jsonify({'success':True, "message": response["content"]})
        
    elif response["type"] == "web":
        wknowledge = ""
        info = web_search(response["content"])
        index.upsert_records(
            "default",
            [
                {
                    "_id": search['question'],
                    'chunk_text': info,
                    "category": "FAQ"
                }
            ]
        )
        prompt = f"""
        A response to the following conversation is to be provided given the knowledge.

        ### Message History
        {data}

        ### Web Knowledge
        {wknowledge}
        """
        response = Assistant.gen(prompt)
        print(response)
        response = json.loads(response)
        print(response["type"])
        if response["type"] == "answer":
            return jsonify({'success':True, "message": response["content"]})
        elif response["type"] == "vector":
            vknowledge = ""
            search = index.search(
                namespace = "default",
                query = {
                    "inputs": {"text": response["content"]},
                    "top_k": 4
                },
                fields = ["category", "chunk_text"],
                rerank = {
                    "model": "bge-reranker-v2-m3",
                    "top_n": 4,
                    "rank_fields": ["chunk_text"] 
                }
            )
            print("SEARCH RESULT ", search)
            n = len(search['result']['hits'])
            vknowledge = [
                search['result']['hits'][i]['fields']['chunk_text'] for i in range(n) if search['result']['hits'][i]['_score'] > 0.6
            ]
            prompt = f"""
            A response to the following conversation is to be provided given the knowledge.

            ### Message History
            {data}

            ### Vector Knowledge
            {vknowledge}

            ### Web Knowledge
            {wknowledge}
            """
            response = Assistant.gen(prompt)
            print(response)
            response = json.loads(response)
            return jsonify({'success':True, "message": response["content"]})


@app.route("/voice-to-text", methods=["GET","POST"])
def voice_to_text():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400

    audio_file = request.files['audio']
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
        audio_file.save(temp_audio.name)
        audio_path = temp_audio.name

    try:
        with open(audio_path, "rb") as f:
            upload_response = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f})
        
        upload_data = upload_response.json()
        file_url = upload_data['data']['url']
    except Exception as e:
        return jsonify({'error': 'Upload failed', 'details': str(e)}), 500

    
    try:
        print(file_url[:20]+"dl/"+file_url[20:])
        result = stt.run(file_url[:20]+"dl/"+file_url[20:])  
        print("RESULT: ", result)
        return jsonify({'text': result})
    except Exception as e:
        return jsonify({'error': 'STT failed', 'details': str(e)}), 500
    
@app.route("/kokorofy", methods=["GET","POST"])
def kokorofy():
    data = request.get_json()
    text = data['messages']
    print(text)
    input = {
        "text": text,
        "voice": "af_bella"
    }
    output = replicate.run(
        "jaaari/kokoro-82m:f559560eb822dc509045f3921a1921234918b91739db4bf3daab2169b71c7a13",
        input=input
    )
    return jsonify({"url": str(output)})

        


if __name__ == "__main__":
    app.run(debug=True)
