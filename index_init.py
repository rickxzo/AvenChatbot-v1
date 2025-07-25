from pinecone import Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

index_name = "avenchatbot"

if not pc.has_index(index_name):
    pc.create_index_for_model(
        name=index_name,
        cloud="aws",
        region="us-east-1",
        embed={
            "model":"llama-text-embed-v2",
            "field_map":{"text": "chunk_text"}
        }
    )


print(pc.describe_index("avenchatbot"))
