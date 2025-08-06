import os
from dotenv import load_dotenv
load_dotenv()

from mcp.server.fastmcp import FastMCP
mcp = FastMCP("AvenMCP", host="0.0.0.0")

from pinecone import Pinecone
pine_api = os.getenv("PINECONE_API_KEY")
pc = Pinecone(api_key=pine_api)
index = pc.Index(host="avenchatbot-rz0q9xs.svc.aped-4627-b74a.pinecone.io")

from exa_py import Exa
exa_api = os.getenv("EXA_API_KEY")
exa = Exa(api_key = exa_api)

import replicate
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

class TextModel:
    def __init__(self, model_name, system_prompt):
        self.model_name = model_name
        self.system_prompt = system_prompt
    
    def gen(self, prompt):
        input = {
            "prompt": prompt,
            "system_prompt": self.system_prompt,
        }
        x = ''
        for event in replicate.stream(
            self.model_name,
            input=input
        ):
            x += str(event)
        x = x.replace('\\', '\\\\')
        return x
    
Summarizer = TextModel(
    "openai/o4-mini",
    "Given an amount of text, compile it into a smaller text while not losing content."
)

@mcp.resource("vector://{prompt}")
def get_vector(prompt):
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

@mcp.resource("web://{query}")
def web_search(query):
    result = str(exa.search_and_contents(
        query,
        type = "auto",
        num_results = 5,
        summary = True
    )).split("\n")
    summ = []
    for i in result:
        if "Summary:" in i:
            summ.append(i[9:])
    summary = Summarizer.gen(" ".join(summ))
    return summary

if __name__ == "__main__":
    mcp.run(transport="sse")