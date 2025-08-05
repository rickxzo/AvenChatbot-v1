# AvenChatbot-v1
A chatbot made to answer Aven's user queries.
Try it on Render - https://avenchatbot-v1.onrender.com

This chatbot can
- Provide information via Web Search or IndexDB Search.
- Text-to-Text Conversations
- Audio-to-Text Conversations
- Audio-to-Audio Conversations (Live Calls)

This chatbot uses
- AI Inference (Replicate)
- RAG Knowledge Base (Pinecone)
- Web Research & Crawl (Exa.ai)
- Prompt Engineering for recall

Technical Stack:
- Frontend -> Vue.js, TailwindCSS
- Backend -> Flask
- Database -> Pinecone (for RAG)

Architecture:

- T2T => user prompt -> Index Searcher (Searches index for relevant info IF needed) -> Web Searcher (Searches web for relevant info IF needed) -> Assistant (Provides final output based on prompts & information retrieved by searching layers).
- A2T => user audio -> STTModel -> same workflow as T2T.
- A2A => user audio -> STTModel -> T2T workflow -> TTSModel -> Audio Player.

Future improvement scope -
- Streaming Text Responses
- Realtime Model integration
- Tool context model architecture
- Response time-consumption optimization

How to use?
- Install dependencies
- Get API keys from Replicate, Exa.AI, Pinecone
- Set env vars with API keys as values.
- run index_init.py to init a Pinecone IndexDB, note the host.
- edit index_modify.py with Pinecone host & desired web crawl target url.
- run kokoro.py to init voice call introductory voice, note the url.
- edit /static/chatbot.js Chatbot component method start_call() line 3 url.
- run flask app.  // ALWAYS app.py. ALL app(vn).py are older code with lesser optimization.

Refer to sample usage video of source code.

This project was made as a part of Headstarter Buildcore Beta fellowship program.
