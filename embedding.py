import pinecone
from sentence_transformers import SentenceTransformer
import torch
import math

# Determine device: use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

def generate_and_store_embeddings(chunks, index, batch_size=100):
    """
    Generate embeddings for chunks and store them in Pinecone in batches
    
    Args:
    - chunks: List of chunk dictionaries with text and optional source
    - index: Pinecone index to upsert vectors
    - batch_size: Number of vectors to upsert in each batch (default 100)
    """
    # Initialize embedding model
    embedding_model = SentenceTransformer("all-mpnet-base-v2", device=device)
    
    # Calculate total number of batches
    total_chunks = len(chunks)
    total_batches = math.ceil(total_chunks / batch_size)
    
    # Generate and upsert embeddings in batches
    for batch_num in range(total_batches):
        # Calculate start and end indices for current batch
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, total_chunks)
        
        # Select current batch of chunks
        current_batch = chunks[start_idx:end_idx]
        
        # Generate vectors for current batch
        vectors = []
        for i, chunk in enumerate(current_batch):
            # Create unique ID by combining batch number and chunk index
            unique_id = f"{batch_num}_{i}"
            
            # Generate embedding
            embedding = embedding_model.encode(chunk["text"]).astype("float32").tolist()
            
            vectors.append({
                "id": unique_id,
                "values": embedding,
                "metadata": {
                    "text": chunk["text"],
                    "source": chunk.get("source", "unknown")
                }
            })
        
        # Upsert current batch of vectors
        try:
            index.upsert(vectors=vectors)
            print(f"✅ Batch {batch_num + 1}/{total_batches}: {len(vectors)} vectors upserted.")
        except Exception as e:
            print(f"❌ Error upserting batch {batch_num + 1}: {str(e)}")
    
    print(f"🎉 Total {total_chunks} chunks processed and upserted successfully.")
