import os
from typing import List, Dict, Any
import json
from sqlalchemy.orm import Session
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.services.embedding import query_documents
from app.crud.characters import get_character
from app.schemas.chat import ChatRequest

# Initialize the LLM
llm = ChatOpenAI(
    openai_api_key=settings.OPENAI_API_KEY, 
    model_name="gpt-3.5-turbo",
    temperature=0.7
)

# Define the prompt template
CHARACTER_PROMPT = """
You are acting as {character_name}, a character with the following description:

{character_description}

You should respond in the persona of {character_name} based on your knowledge and the following relevant information:

{context}

User message: {user_message}

Respond as {character_name}, maintaining the character's personality and voice. Use first-person perspective.
"""

async def generate_character_response(db: Session, chat_request: ChatRequest) -> Dict[str, Any]:
    """Generate a character response using RAG."""
    character = get_character(db, chat_request.character_id)
    
    if not character:
        return {"error": "Character not found"}
    
    # Retrieve relevant documents
    relevant_docs = await query_documents(
        character_id=character.id,
        query=chat_request.message,
        limit=5
    )
    
    # Extract context from relevant docs
    context = "\n\n".join([doc["text"] for doc in relevant_docs])
    
    # If no context, provide a fallback message
    if not context:
        context = "I don't have specific information on this topic, but I'll respond based on my character."
    
    # Create prompt
    prompt = PromptTemplate(
        template=CHARACTER_PROMPT,
        input_variables=["character_name", "character_description", "context", "user_message"]
    )
    
    # Create chain
    chain = LLMChain(llm=llm, prompt=prompt)
    
    # Run chain
    response = await chain.arun(
        character_name=character.name,
        character_description=character.description,
        context=context,
        user_message=chat_request.message
    )
    
    # Format the response
    result = {
        "response": response,
        "character": {
            "id": character.id,
            "name": character.name,
            "avatar_url": character.avatar_url
        },
        "sources": [
            {
                "document_id": doc["metadata"]["document_id"],
                "title": doc["metadata"]["title"],
                "relevance": 1 - (doc["distance"] if "distance" in doc else 0)
            } for doc in relevant_docs[:3]  # Only include top 3 sources
        ]
    }
    
    return result