import faiss
import pickle
import os
import numpy as np
from .config import INDEX_FILE, METADATA_FILE

class VectorStore:
    def __init__(self):
        self.index = None
        self.metadata = []
        self.load()

    def load(self):
        if os.path.exists(INDEX_FILE) and os.path.exists(METADATA_FILE):
            print(f"Loading index from {INDEX_FILE}")
            self.index = faiss.read_index(INDEX_FILE)
            with open(METADATA_FILE, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            print("No existing index found. Starting fresh.")
            self.index = None
            self.metadata = []

    def save(self):
        if self.index:
            faiss.write_index(self.index, INDEX_FILE)
        with open(METADATA_FILE, 'wb') as f:
            pickle.dump(self.metadata, f)

    def clear(self):
        """Clears the index and metadata"""
        self.index = None
        self.metadata = []
        # Delete files if they exist
        if os.path.exists(INDEX_FILE):
            os.remove(INDEX_FILE)
        if os.path.exists(METADATA_FILE):
            os.remove(METADATA_FILE)
        print("Vector store cleared.")

    def add_documents(self, embeddings, metas):
        if not embeddings:
            return
        
        vectors = np.array(embeddings).astype('float32')
        
        # Reload index from disk just in case it was created by another process/request
        # This is a simple concurrency handling for this specific single-worker-but-reloaded case
        if os.path.exists(INDEX_FILE) and os.path.exists(METADATA_FILE):
             try:
                disk_index = faiss.read_index(INDEX_FILE)
                # Only reload if disk has MORE data or different pointer, 
                # but careful not to overwrite memory-only changes if we were doing batching (we aren't).
                if self.index is None or disk_index.ntotal != self.index.ntotal:
                    self.index = disk_index
                    with open(METADATA_FILE, 'rb') as f:
                        self.metadata = pickle.load(f)
             except Exception as e:
                 print(f"Warning: Failed to reload index from disk: {e}")

        if self.index is None:
            print("Creating new FAISS index...")
            self.index = faiss.IndexFlatL2(vectors.shape[1])
        
        self.index.add(vectors)
        self.metadata.extend(metas)
        self.save()
        print(f"Saved {len(embeddings)} new vectors. Total: {self.index.ntotal}")


    def delete_file(self, filename, person_id):
        """
        Deletes all vectors associated with a specific file and person.
        Since IndexFlatL2 doesn't support random deletion, we have to rebuild the index.
        """
        # Reload latest
        self.load()
        
        if self.index is None or not self.metadata:
            return False

        print(f"Deleting file {filename} for person {person_id} from index...")
        
        # Identify indices to keep
        keep_indices = []
        new_metadata = []
        
        for i, meta in enumerate(self.metadata):
            # Check if this item matches the file to delete
            if meta.get('filename') == filename and meta.get('person') == person_id:
                continue # Skip this one (delete it)
            
            keep_indices.append(i)
            new_metadata.append(meta)
            
        if len(keep_indices) == len(self.metadata):
            print("No matching documents found in index to delete.")
            return False

        # Rebuild Index
        try:
            # Reconstruct all vectors first
            if self.index.ntotal > 0:
                all_vectors = self.index.reconstruct_n(0, self.index.ntotal)
                new_vectors = all_vectors[keep_indices]
                
                # Create new index
                new_index = faiss.IndexFlatL2(new_vectors.shape[1])
                new_index.add(new_vectors)
                
                self.index = new_index
                self.metadata = new_metadata
                self.save()
                print(f"Successfully deleted vectors. New total: {self.index.ntotal}")
                return True
            return False
            
        except Exception as e:
            print(f"Error rebuilding index during deletion: {e}")
            return False

    def search(self, query_vector, k=5, person_filter=None):
        if self.index is None or self.index.ntotal == 0:
            return []
        
        query_vector = np.array([query_vector]).astype('float32')
        # We search for more than k to allow for filtering
        search_k = k * 5 if person_filter else k
        distances, indices = self.index.search(query_vector, search_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.metadata):
                item = self.metadata[idx]
                if person_filter and item.get('person') != person_filter:
                    continue
                results.append(item)
                if len(results) >= k:
                    break
        return results
