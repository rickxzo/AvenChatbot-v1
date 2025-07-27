from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
load_dotenv()
import json
import os
import tempfile
import requests

from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

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
def vector_search(prompt):
    search = index.search(
            namespace = "default",
            query = {
                "inputs": {"text": prompt},
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
        search['result']['hits'][i]['fields']['chunk_text'] for i in range(n) if search['result']['hits'][i]['_score'] > 0.35
    ]
    return vknowledge

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
    Context: You are Aven's intelligent chat assistant, designed to assist users with their queries—especially those related to financial services, products, or policies offered by Aven (note: Aven might be misspelled as Even, Avian, Evan, etc.).
    
    Instructions:
    - Do not assume information regarding Aven. Only use provided knowledge for answering.
    - Always reply in JSON format.
    - Use any of the provided tools to gather knowledge from sources if need be.

    Output templates:
    1. If query can be answered without need of additional knowledge.
    {
        "type": "answer",
        "content": "<Your concise and polite response here>"
    }
    2. If additional information is needed for answering query.
    {
        "type": "vector"/"web",
        "content": "<Your prompt to search vector/web with>"
    }
    VectorDB has vast information regarding Aven. Web has diverse information on all topics including Aven.
    Always prefer VectorDB search over Web search when either can work.
    The prompt will contain your action history i.e. previous Vector / Web searches.
    Do not use "/" in your replies.
    Answer appropriately when you can not find appropriate knowledge to answer the query.
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

class ProcessState(TypedDict):
    conversation: str
    knowledge: str
    response: str
    reply: str

def choose(state: ProcessState):
    print("Choose ", state)
    conversation = state["conversation"]
    knowledge = state["knowledge"]

    prompt = f"""
    ### Conversation
    {conversation}

    ### Current Knowledge
    {knowledge}

    ### Available Actions
    vector, web
    """
    response = Assistant.gen(prompt)
    return {
        "response": response
    }

def route(state: ProcessState) -> str:
    response = state["response"]
    response = json.loads(response)
    return response["type"]

def go_web(state: ProcessState):
    print("GOWEB", state)
    response = state["response"]
    response = json.loads(response)
    info = web_search(response["content"])
    knowledge = state["knowledge"]
    knowledge += f"""
    -> WEB SEARCH "{response["content"]}" KNOWLEDGE
    {info}
    """
    return {
        "knowledge": knowledge
    }

def go_vector(state: ProcessState):
    print("GOVECTOR", state)
    response = json.loads(state["response"])
    info = vector_search(response["content"])
    knowledge = state["knowledge"]
    knowledge += f"""
    -> VECTOR SEARCH "{response["content"]}" KNOWLEDGE
    {info}
    """
    return {
        "knowledge": knowledge
    }

def give_reply(state: ProcessState):
    print("SENDREPLY", state)
    response = json.loads(state["response"])
    reply = response["content"]
    return {
        "reply": reply
    }


chat_graph = StateGraph(ProcessState)
chat_graph.add_node("choose", choose)
chat_graph.add_node("go_web", go_web)
chat_graph.add_node("go_vector", go_vector)
chat_graph.add_node("give_reply", give_reply)

chat_graph.add_edge(START, "choose")
chat_graph.add_conditional_edges(
    "choose",
    route,
    {
        "answer": "give_reply",
        "web": "go_web",
        "vector": "go_vector"
    }
)
chat_graph.add_edge("go_web", "choose")
chat_graph.add_edge("go_vector", "choose")
chat_graph.add_edge("give_reply", END)

compiled_graph = chat_graph.compile()

app = Flask(__name__, template_folder=".", static_folder="static")
app.secret_key = "aven01"


@app.route("/", methods=["GET","POST"])
def home():
    return render_template("chatbot.html")


@app.route("/respond", methods=["GET", "POST"])
def respond():
    data = request.get_json()
    messages = data['messages']
    conversation = "\n".join(f"{msg['from']}: {msg['text']}" for msg in messages)
    print(conversation)
    
    final_state = compiled_graph.invoke({
        "conversation": conversation,
        "knowledge": "",
        "response": ""
    })
    k = final_state['reply'].replace("\\n","<br>")
    print(k)
    return jsonify({
        "success": True,
        "message": k
    })
    


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
