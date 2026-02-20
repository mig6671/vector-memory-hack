#!/usr/bin/env python3
"""
Vector Memory Hack - Ultra-lightweight semantic search
Zero dependencies, pure Python + SQLite
"""

import sqlite3
import re
import math
import json
import os
from typing import List, Tuple, Optional

class VectorMemory:
    """
    Lightweight semantic memory using SQLite and simple vector similarity.
    No heavy ML libraries required - uses character n-gram hashing for embeddings.
    """
    
    def __init__(self, db_path: str = "memory.db", dim: int = 128):
        self.db_path = db_path
        self.dim = dim
        self.conn = sqlite3.connect(db_path)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite schema."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                embedding BLOB NOT NULL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)
        """)
        self.conn.commit()
    
    def _simple_hash(self, text: str) -> List[float]:
        """
        Create simple embedding using character n-gram hashing.
        Fast, deterministic, no external dependencies.
        """
        # Normalize text
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', '', text)
        
        # Character n-grams (2-4 chars)
        ngrams = []
        for n in [2, 3, 4]:
            for i in range(len(text) - n + 1):
                ngrams.append(text[i:i+n])
        
        # Hash to fixed dimension
        embedding = [0.0] * self.dim
        for i, ngram in enumerate(ngrams):
            hash_val = hash(ngram) % self.dim
            embedding[hash_val] += 1.0
        
        # Normalize
        magnitude = math.sqrt(sum(x*x for x in embedding))
        if magnitude > 0:
            embedding = [x/magnitude for x in embedding]
        
        return embedding
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot = sum(x*y for x, y in zip(a, b))
        return dot  # Already normalized
    
    def add(self, content: str, metadata: Optional[dict] = None) -> int:
        """
        Add a memory entry.
        
        Args:
            content: Text to store
            metadata: Optional JSON-serializable metadata
            
        Returns:
            Memory ID
        """
        embedding = self._simple_hash(content)
        embedding_blob = json.dumps(embedding).encode()
        metadata_json = json.dumps(metadata) if metadata else None
        
        cursor = self.conn.execute(
            "INSERT INTO memories (content, embedding, metadata) VALUES (?, ?, ?)",
            (content, embedding_blob, metadata_json)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, str, float, Optional[dict]]]:
        """
        Search for similar memories.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of (id, content, similarity_score, metadata) tuples
        """
        query_embedding = self._simple_hash(query)
        
        # Fetch all memories (for small-medium datasets)
        # For large datasets, implement approximate nearest neighbors
        cursor = self.conn.execute(
            "SELECT id, content, embedding, metadata FROM memories ORDER BY created_at DESC LIMIT 1000"
        )
        
        results = []
        for row in cursor:
            mem_id, content, embedding_blob, metadata_json = row
            mem_embedding = json.loads(embedding_blob.decode())
            similarity = self._cosine_similarity(query_embedding, mem_embedding)
            metadata = json.loads(metadata_json) if metadata_json else None
            results.append((mem_id, content, similarity, metadata))
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:top_k]
    
    def delete(self, memory_id: int) -> bool:
        """Delete a memory by ID."""
        cursor = self.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def clear(self):
        """Clear all memories."""
        self.conn.execute("DELETE FROM memories")
        self.conn.commit()
    
    def stats(self) -> dict:
        """Get memory statistics."""
        cursor = self.conn.execute("SELECT COUNT(*), MAX(created_at), MIN(created_at) FROM memories")
        count, newest, oldest = cursor.fetchone()
        return {
            "count": count,
            "newest": newest,
            "oldest": oldest,
            "db_path": self.db_path,
            "db_size_bytes": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        }
    
    def close(self):
        """Close database connection."""
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def main():
    """CLI interface for Vector Memory Hack."""
    import sys
    
    if len(sys.argv) < 2:
        print("Vector Memory Hack - Usage:")
        print("  python vector_memory.py add 'Your memory text here'")
        print("  python vector_memory.py search 'query text'")
        print("  python vector_memory.py stats")
        print("  python vector_memory.py clear")
        sys.exit(1)
    
    command = sys.argv[1]
    
    with VectorMemory() as mem:
        if command == "add" and len(sys.argv) >= 3:
            content = sys.argv[2]
            mem_id = mem.add(content)
            print(f"✅ Added memory #{mem_id}")
            
        elif command == "search" and len(sys.argv) >= 3:
            query = sys.argv[2]
            results = mem.search(query)
            print(f"\n🔍 Search results for: '{query}'\n")
            for mem_id, content, score, meta in results:
                print(f"  #{mem_id} [score: {score:.3f}]")
                print(f"     {content[:100]}...")
                if meta:
                    print(f"     meta: {meta}")
                print()
                
        elif command == "stats":
            stats = mem.stats()
            print("📊 Memory Statistics:")
            for key, val in stats.items():
                print(f"  {key}: {val}")
                
        elif command == "clear":
            mem.clear()
            print("🗑️ All memories cleared")
            
        else:
            print("Unknown command or missing arguments")
            sys.exit(1)


if __name__ == "__main__":
    main()
