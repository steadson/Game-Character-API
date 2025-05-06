import chromadb
import os
from chromadb.config import Settings
import logging
from app.core.config import settings
chroma_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "chroma_db")

def delete_from_chroma(document_id: int) -> None:
    """
    Delete a document's embeddings from ChromaDB.
    """
    try:
        # Initialize ChromaDB client
        chroma_client = chromadb.PersistentClient(
            path=chroma_db_path
        )
        
        # Get the collection
        collection = chroma_client.get_collection(name="documents_embeddings")
        # Query to find all chunks associated with this document
        results = collection.get(
            where={"doc_id": document_id}
        )
        if results and results["ids"]:
            # Delete all chunks associated with this document
            collection.delete(ids=results["ids"])
            logging.info(f"Successfully deleted {len(results['ids'])} chunks for document {document_id} from ChromaDB")
        else:
            # Try the old way - direct ID deletion
            # This is for backward compatibility with documents that might have been embedded
            # before chunking was implemented
            collection.delete(ids=[f"doc_{document_id}"])
            logging.info(f"Successfully deleted document {document_id} from ChromaDB using legacy ID format")
    except Exception as e:
        logging.error(f"Error deleting document {document_id} from ChromaDB: {str(e)}")