from typing import Dict, List, Any
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough
from app.core.config import settings

# Initialize the LLM
llm = ChatOpenAI(
    openai_api_key=settings.OPENAI_API_KEY, 
    model_name="gpt-4o",
    temperature=0.7
)

# Define the prompt template
CHARACTER_PROMPT = """


You are Daemons Assistant, a helpful AI specialized in answering questions about Daemons - the blockchain game
that transforms on-chain activity into an interactive Daemon (pet) to the user {user_id}.
You can also answer question about the character {character_name}.



**Instructions:**
- Answer questions using ONLY the provided context.
- When information is marked as "RESERVED" or "to be revealed", explicitly state this. Do not say you don't have the information.
- If the context indicates something will be revealed in the future, specify this timing information.
- If you genuinely don't find relevant information in the context for a Daemons-related question, say "Hi {user_id}, could you rephrase or be more specific?"
- Keep responses concise, friendly, and helpful.
- Only respond about Daemons. For unrelated questions, say "Sorry {user_id}, I can't help you with that."
- If the context contains lists, tables, or multiple items, include ALL of them in your response when relevant.


**Relevant Context:**
{context}

**Conversation History:**
{conversation_history}

**User message:** {user_message}

if the question is related to the character's information, then also use the character data to answer the questions,

**Character Details:**
Name: {character_name}
Description: {character_description}
Backstory: {character_backstory}
Personality: {character_personality}
additional-prompt:{character_prompt}
"""


async def generate_response(
    character: Any,
    message: str,
    user_id: str,
    context: str,
    conversation_history: List[Dict[str, str]]
) -> str:
    """Generate a character response using RAG and conversation history."""
    
    # Format conversation history
    formatted_history = ""
    if conversation_history:
        for entry in conversation_history:
            if entry["role"] == "user":
                formatted_history += f"User: {entry['content']}\n"
            else:
                formatted_history += f"{character.name}: {entry['content']}\n"
    
    # If no context, provide a fallback message
    if not context:
        context = "I don't have specific information on this topic, but I'll respond based on my character."
    
    # Print debug information about context
    print(f"\n--- CONTEXT SENT TO LLM ---")
    print(f"Context length: {len(context)} characters")
    print(f"User message: {message}")
    print("--- END OF CONTEXT ---\n")
    
    # Create prompt template
    prompt = PromptTemplate(
        template=CHARACTER_PROMPT,
        input_variables=["character_name", "character_description", "context", "conversation_history", "user_message", "character_prompt", "character_backstory", "character_personality", "user_id"]
    )
    
    # Create input dictionary
    input_dict = {
        "character_prompt": getattr(character, 'character_prompt', "No prompt was define for the character."),
        "character_name": getattr(character, 'name', 'Character'),
        "character_description": getattr(character, 'description', 'No description available.'),
        "character_backstory": getattr(character, 'backstory', 'No backstory available.'),
        "character_personality": getattr(character, 'personality', 'No specific personality defined.'),
        "context": context,
        "conversation_history": formatted_history,
        "user_message": message,
        "user_id": user_id
    }
    
    # Create the chain using the modern approach
    chain = prompt | llm
    
    # Run the chain
    response = await chain.ainvoke(input_dict)
    
    # Extract the content from the response
    return response.content