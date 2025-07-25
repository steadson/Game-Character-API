from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
# from app.services.embedding import hybrid_query_documents 
from app.db.session import get_db
from app.dependencies import get_api_key
from app.crud import characters, conversation
from app.services.embedding import query_documents # Add this line
# from app.services.rag import query_documents
from app.services.llm import generate_response

router = APIRouter()


class PublicChatRequest(BaseModel):
    user_id: str
    character_id: Any
    message: str


class PublicChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=PublicChatResponse)
async def public_chat(
    *,
    db: Session = Depends(get_db),
    chat_request: PublicChatRequest,
    api_key: Any = Depends(get_api_key)
) -> Any:
    """
    Public chat endpoint that requires an API key.
    Maintains conversation history for each user-character pair.
    """
    # Validate character exists
    character = characters.get_by_character_id(db, character_id=chat_request.character_id)
    if not character:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found"
        )
    
    # Get conversation history
    conversation_history = conversation.get_user_character_history(
        db, 
        user_id=chat_request.user_id, 
        character_id=chat_request.character_id
    )
    
    # Format conversation history for the LLM
    formatted_history = []
    for conv in reversed(conversation_history):  # Oldest first
        formatted_history.append({"role": "user", "content": conv.message})
        formatted_history.append({"role": "assistant", "content": conv.response})
    
    # Retrieve relevant documents using RAG
    relevant_docs = await query_documents(
        character_id=character.character_id,
        query_text=chat_request.message, # Changed 'query' to 'query_text'
        top_k=7                         # Changed 'limit' to 'top_k'
    )
    # relevant_docs = await hybrid_query_documents(
    # character_id=character.character_id,
    # query_text=chat_request.message,
    # top_k=7)
    # Extract context from relevant docs with metadata
    formatted_docs = []
    for doc in relevant_docs:
        # Format each document with its metadata
        doc_text = f"Source: {doc['metadata'].get('document_title', 'Unknown')}"
        
        # Add URL if available
        if 'url' in doc['metadata']:
            doc_text += f" (URL: {doc['metadata']['url']})"
        
        # # Add relevance score
        # doc_text += f"\nRelevance: {doc['relevance_score']:.2f}\n\n"
        
        # Add the actual content
        doc_text += doc['text']
        
        formatted_docs.append(doc_text)

    # Join all formatted documents
    context = "\n\n---\n\n".join(formatted_docs)
    print ('Documents retrieved >>', context)

    # Generate response using LLM
    response = await generate_response(
        character=character,
        message=chat_request.message,
        user_id=chat_request.user_id,
        context=context,
        conversation_history=formatted_history
    )
    
    # Save the conversation
    conversation.create_conversation(
        db,
        user_id=chat_request.user_id,
        character_id=chat_request.character_id,
        message=chat_request.message,
        response=response
    )
    
    return {"response": response}