import pinecone
from sentence_transformers import SentenceTransformer
import torch

# Determine device: use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Load embedding model
model = SentenceTransformer('all-mpnet-base-v2', device=device)

def generate_and_store_embeddings(chunks, index):
    """
    Generate embeddings for chunks and store them in Pinecone
    """
    # Initialize embedding model
    embedding_model = SentenceTransformer("all-mpnet-base-v2")
    
    # Generate embeddings and prepare vectors for Pinecone
    vectors = []
    for i, chunk in enumerate(chunks):
        embedding = embedding_model.encode(chunk["text"]).astype("float32").tolist()
        vectors.append({
            "id": str(i),
            "values": embedding,
            "metadata": {
                "text": chunk["text"],
                "source": chunk.get("source", "unknown")
            }
        })
    
    # Upsert vectors into Pinecone
    index.upsert(vectors=vectors)
    print(f"✅ {len(vectors)} vectors upserted into Pinecone.")
