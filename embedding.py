import pinecone
from sentence_transformers import SentenceTransformer
import torch
import math

# Determine device: use GPU if available
device = "cuda" if torch.cuda.is_available() else "cpu"

def generate_and_store_embeddings(chunks, index, batch_size=50, progress_callback=None):
    """
    Generate embeddings for chunks and store them in Pinecone with detailed batch-wise progress.
    
    Args:
    - chunks: List of chunk dictionaries with text and optional source.
    - index: Pinecone index to upsert vectors.
    - batch_size: Number of vectors to upsert in each batch.
    - progress_callback: Callback function for progress updates.
    
    Returns:
    - Dictionary with processing statistics
    """
    # Initialize embedding model
    embedding_model = SentenceTransformer("all-mpnet-base-v2", device=device)
    
    # Calculate total number of batches
    total_chunks = len(chunks)
    total_batches = math.ceil(total_chunks / batch_size)
    
    # Progress tracking dictionary
    batch_progress = {
        "total_chunks": total_chunks,
        "total_batches": total_batches,
        "processed_chunks": 0,
        "processed_batches": 0
    }
    
    # Main batch processing loop
    for batch_num in range(total_batches):
        try:
            # Calculate batch indices
            start_idx = batch_num * batch_size
            end_idx = min((batch_num + 1) * batch_size, total_chunks)
            current_batch = chunks[start_idx:end_idx]
            
            # Generate embeddings for current batch
            vectors = []
            for i, chunk in enumerate(current_batch):
                unique_id = f"chunk_{batch_num}_{i}"
                
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
            
            # Upsert current batch
            index.upsert(vectors=vectors)
            
            # Update progress
            batch_progress["processed_chunks"] += len(current_batch)
            batch_progress["processed_batches"] += 1
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback(
                    current_batch=batch_num + 1,
                    total_batches=total_batches,
                    batch_size=len(current_batch),
                    batch_progress=batch_progress
                )
        
        except Exception as e:
            print(f"Error processing batch {batch_num + 1}: {str(e)}")
            continue
    
    return batch_progress
