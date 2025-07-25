from exa_py import Exa
exa = Exa(api_key = "1bf7c651-3c14-4128-a425-6863c1fd6d5a")

from pinecone import Pinecone
pc = Pinecone(api_key="pcsk_78zW9c_JTy8hG5rCwEqsRTNZGiFzwykKa8gD6pgVPTq1d8vSjso2BU7Xj7hQ7s6pkDzbDC")
index = pc.Index(host="avenchatbot-rz0q9xs.svc.aped-4627-b74a.pinecone.io")

result = str(exa.get_contents(
  ["aven.com/support"],
  text = True
))[678:-5624]


import re

pattern = r'-\s.*?\?\s*!\[down\]\(.*?\)'

matches = list(re.finditer(pattern, result))

def to_ascii_id(text):
    return text.encode("ascii", "ignore").decode().strip()

results = []

for i in range(len(matches)):
    start = matches[i].start()
    end = matches[i+1].start() if i + 1 < len(matches) else len(result)
    block = result[start:end].strip()
    block = block.split(" ![down]")
    block[0] = block[0][2:]
    block[1] = block[1][45:]
    index.upsert_records(
        "default",
        [
            {
                "_id": to_ascii_id(block[0]),
                "chunk_text": block[1],
                "category": "FAQ"
            }
        ]
    )
    print(f"{i}/{len(matches)}")



