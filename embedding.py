import pinecone
from sentence_transformers import SentenceTransformer
import torch

# Determine device: use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Load embedding model
model = SentenceTransformer('all-mpnet-base-v2', device=device)

def generate_and_store_embeddings(chunks, pinecone_index):
    texts = [chunk['text'] for chunk in chunks]
    metadata = [chunk['metadata'] for chunk in chunks]

    # Generate embeddings
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    # Store embeddings in Pinecone
    vectors = []
    for i, (embedding, meta) in enumerate(zip(embeddings, metadata)):
        vector_id = str(i)  # Unique ID for each vector
        vectors.append((vector_id, embedding.tolist(), meta))

    # Upsert vectors into Pinecone
    pinecone_index.upsert(vectors)
    print(f"✅ {len(vectors)} vectors upserted into Pinecone.")
