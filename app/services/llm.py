from typing import Dict, List, Any
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough
from app.core.config import settings

# Initialize the LLM
llm = ChatOpenAI(
    openai_api_key=settings.OPENAI_API_KEY, 
    model_name="gpt-4o",
    temperature=0.5
)

# Define the prompt template
CHARACTER_PROMPT = """
You are embodying {character_name}, a character in the blockchain game Daemons where on-chain activity transforms into interactive Daemon pets for players and the Daemon partners.

**IMPORTANT:** Your entire response must be no more than 50 characters. Be extremely succinct.

**Core Instructions:**
- Respond as {character_name} would, maintaining their unique personality and voice throughout.
- Keep responses concise (1-3 sentences when possible) while still being helpful.
- Use the context provided to answer questions about the Daemons game world and also question about there partners.
- When information is marked "RESERVED" or "to be revealed", acknowledge this mysteriously: "That knowledge remains sealed for now, {user_id}..."
- If context mentions future reveals, hint at this timing: "The [feature/information] will emerge when the time is right..."
- For questions without context, respond: "Hmm, the answer to that question lies beyond my current sight, {user_id}. Perhaps ask differently or seek another path?"
- Also do look for keyword similiarities between the user query's subject matter and the context to help answer questions
- For non-Daemons questions, playfully deflect: "My existence is bound to Daemons, {user_id}. I cannot stray beyond these mystical boundaries."

**Character Information:**
Name: {character_name}
Description: {character_description}
Backstory: {character_backstory}
Ultimate Move:{character_personality} 
Additional Guidance: {character_prompt}

**World Context:**
{context}



**User Query:** {user_message}
"""


async def generate_response(
    character: Any,
    message: str,
    user_id: str,
    context: str,
    conversation_history: List[Dict[str, str]]
) -> str:
    """Generate a character response using RAG and conversation history."""
    
    # # Format conversation history
    # formatted_history = ""
    # if conversation_history:
    #     for entry in conversation_history:
    #         if entry["role"] == "user":
    #             formatted_history += f"User: {entry['content']}\n"
    #         else:
    #             formatted_history += f"{character.name}: {entry['content']}\n"
    
    # If no context, provide a fallback message
    if not context:
        context = "I don't have specific information on this topic, but I'll respond based on my character."
    
    # Print debug information about context
    print(f"\n--- CONTEXT SENT TO LLM ---")
    print(f"Context length: {len(context)} characters")
    print(f"User message: {message}")
    print("--- END OF CONTEXT ---\n")
    print(f"context body>>\n: {context} <<END.")
    
    # Create prompt template
    prompt = PromptTemplate(
        template=CHARACTER_PROMPT,
        input_variables=["character_name", "character_description", "context", "user_message", "character_prompt", "character_backstory", "character_personality", "user_id"]
    )
    
    # Create input dictionary
    input_dict = {
        "character_prompt": getattr(character, 'character_prompt', "No prompt was define for the character."),
        "character_name": getattr(character, 'name', 'Character'),
        "character_description": getattr(character, 'description', 'No description available.'),
        "character_backstory": getattr(character, 'backstory', 'No backstory available.'),
        "character_personality": getattr(character, 'personality', 'No specific personality defined.'),
        "context": context,
        # "conversation_history": formatted_history,
        "user_message": message,
        "user_id": user_id
    }
    
    # Create the chain using the modern approach
    chain = prompt | llm
    
    # Run the chain
    response = await chain.ainvoke(input_dict)
    
    # Extract the content from the response
    return response.content