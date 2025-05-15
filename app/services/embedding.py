import os
import io
import asyncio
import logging
from typing import Optional, List, Dict, Any
import mimetypes
import uuid
from urllib.parse import urlparse
from datetime import datetime

# File processing libraries
import PyPDF2
import docx
import pandas as pd
import mammoth
import csv
from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright

# Embedding
from openai import OpenAI
import chromadb
from sqlalchemy.orm import Session

# Local imports
from app.core.config import settings
from app.models.document import Document, ContentType
from app.crud.documents import update_document_status

from dotenv import load_dotenv
load_dotenv()
# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Add console handler to make logs appear in the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
# Initialize OpenAI client
openai_api_key = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=openai_api_key)

# Initialize ChromaDB client
chroma_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "chroma_db")
logger.info(f"Using ChromaDB path: {chroma_db_path}")
chroma_client = chromadb.PersistentClient(path=chroma_db_path)
collection_name = "documents_embeddings"

async def process_document(document_id: int, db: Session,  reembed: bool = False) -> None:
    """

    Main function to process a document for embedding.
    
    Args:
        document_id: The ID of the document to process
        db: Database session
    """
    try:
        logger.info(f"Starting document processing for ID: {document_id}")
        # Get document from database
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"Document with ID {document_id} not found")
            return
         # If re-embedding, delete existing embeddings first
        if reembed and document.is_embedded:
            logger.info(f"Re-embedding requested for document ID {document_id}. Deleting old embeddings...")
            from app.services.chroma_utils import delete_from_chroma
            delete_from_chroma(document_id)
            logger.info(f"Old embeddings deleted for document ID {document_id}")
        # Update document status to processing
        update_document_status(db, id=document_id, is_embedded=False, status="processing")
        logger.info(f"Processing document: {document.title} (ID: {document_id})")
        
        # Extract text based on content type
        text_content = None
        
        if document.content_type == ContentType.FILE:
            # Process file based on extension
            file_path = document.file_path
            if not os.path.exists(file_path):
                logger.error(f"File not found at path: {file_path}")
                update_document_status(db, id=document_id, is_embedded=False, status="failed")
                return
                
            file_extension = os.path.splitext(document.original_filename)[1].lower()
            
            try:
                if file_extension in ['.pdf']:
                    text_content = extract_text_from_pdf(file_path)
                elif file_extension in ['.docx']:
                    text_content = extract_text_from_docx(file_path)
                elif file_extension in ['.doc']:
                    text_content = extract_text_from_doc(file_path)
                elif file_extension in ['.xlsx', '.xls']:
                    text_content = extract_text_from_excel(file_path)
                elif file_extension in ['.csv']:
                    text_content = extract_text_from_csv(file_path)
                elif file_extension in ['.txt', '.md', '.json', '.html', '.xml']:
                    text_content = extract_text_from_text_file(file_path)
                else:
                    logger.warning(f"Unsupported file type: {file_extension}")
                    text_content = extract_text_from_text_file(file_path)  # Try as text file anyway
            except Exception as e:
                logger.error(f"Error extracting text from file: {str(e)}")
                update_document_status(db, id=document_id, is_embedded=False, status="failed")
                return
                
        elif document.content_type == ContentType.TEXT:
            # For text content, read the file and get the content
            try:
                with open(document.file_path, "r", encoding="utf-8") as f:
                    text_content = f.read()
                logger.info(f"Extracted text content from document (length: {len(text_content)} chars)")
            except Exception as e:
                logger.error(f"Error reading text content: {str(e)}")
                update_document_status(db, id=document_id, is_embedded=False, status="failed")
                return
                
        elif document.content_type == ContentType.LINK:
            # For links, scrape the content
            try:
                url = document.file_path
                # Use Playwright for better handling of dynamic content
                text_content = await scrape_with_playwright(url)
                if not text_content:
                    # Fallback to simple requests if Playwright fails
                    text_content = scrape_with_requests(url)
                logger.info(f"Scraped content from URL: {url} (length: {len(text_content)} chars)")
            except Exception as e:
                logger.error(f"Error scraping URL content: {str(e)}")
                update_document_status(db, id=document_id, is_embedded=False, status="failed")
                return
        
        # If no text content was extracted, mark as failed
        if not text_content or len(text_content.strip()) == 0:
            logger.error(f"No text content extracted from document ID {document_id}")
            update_document_status(db, id=document_id, is_embedded=False, status="failed")
            return
        if text_content:
            preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
            logger.info(f"Extracted text content preview: {preview}")
        # Process the text content for embedding
        try:
            # Create chunks from the text content
            chunks = chunk_text(text_content, document.title, document.id)
            logger.info(f"Created {len(chunks)} chunks from document")
            
            # Create embeddings and store in vector database
            await create_embeddings(chunks, document)
            
            # Update document status to embedded
            update_document_status(db, id=document_id, is_embedded=True, status="embedded")
            logger.info(f"Successfully embedded document ID {document_id}")
            
        except Exception as e:
            logger.error(f"Error during embedding process: {str(e)}")
            update_document_status(db, id=document_id, is_embedded=False, status="failed")
            
    except Exception as e:
        logger.error(f"Unexpected error processing document {document_id}: {str(e)}")
        update_document_status(db, id=document_id, is_embedded=False, status="failed")

# Add the missing query_documents function
async def query_documents(query_text: str, top_k: int = 5, character_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Query the document embeddings to find relevant content for a given query.
    
    Args:
        query_text: The query text to search for
        top_k: Number of results to return
        character_id: Optional character ID to filter results
        
    Returns:
        List of relevant document chunks with metadata
    """
    logger.info(f"Querying documents with: '{query_text}'")
    
    try:
        # Get the collection
        collection = chroma_client.get_collection(name=collection_name)
        
        # Create embedding for the query
        response = openai_client.embeddings.create(
            input=query_text,
            model="text-embedding-3-large"  # Use the same model as for document embeddings
        )
        query_embedding = response.data[0].embedding
        
        # Query the collection
        filter_dict = {}
        if character_id is not None:
            filter_dict["character_id"] = character_id
            
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            # where=filter_dict if filter_dict else None,
            include=["documents", "metadatas", "distances"]
        )
        # print(results)
        # Format results
        formatted_results = []
        if results and results["documents"] and len(results["documents"][0]) > 0:
            for i, (doc, metadata, distance) in enumerate(zip(
                results["documents"][0], 
                results["metadatas"][0],
                results["distances"][0]
            )):
                formatted_results.append({
                    "text": doc,
                    "metadata": metadata,
                    "relevance_score": 1.0 - distance,  # Convert distance to similarity score
                    "rank": i + 1
                })
            
            logger.info(f"Found {len(formatted_results)} relevant document chunks")
        else:
            logger.info("No relevant documents found")
            
        return formatted_results
        
    except Exception as e:
        logger.error(f"Error querying documents: {str(e)}")
        return []

# async def hybrid_query_documents(query_text: str, top_k: int = 5, character_id: Optional[int] = None) -> List[Dict[str, Any]]:
#     """
#     Perform hybrid search combining vector similarity and keyword matching
    
#     Args:
#         query_text: The query text to search for
#         top_k: Number of results to return
#         character_id: Optional character ID to filter results
        
#     Returns:
#         List of relevant document chunks with metadata
#     """
#     logger.info(f"Performing hybrid search with: '{query_text}'")
    
#     try:
#         # Get the collection
#         collection = chroma_client.get_collection(name=collection_name)
        
#         # Create embedding for the query (do this only once)
#         response = openai_client.embeddings.create(
#             input=query_text,
#             model="text-embedding-3-large"
#         )
#         query_embedding = response.data[0].embedding
        
#         # Perform a single hybrid search using ChromaDB's built-in capabilities
#         filter_dict = {}
#         if character_id is not None:
#             filter_dict["character_id"] = character_id
            
#         results = collection.query(
#             query_embeddings=[query_embedding],
#             query_texts=[query_text],  # Add text query for hybrid search
#             n_results=top_k,
#             where=filter_dict if filter_dict else None,
#             include=["documents", "metadatas", "distances"]
#         )
        
#         # Format results
#         formatted_results = []
#         if results and results["documents"] and len(results["documents"][0]) > 0:
#             for i, (doc, metadata, distance) in enumerate(zip(
#                 results["documents"][0], 
#                 results["metadatas"][0],
#                 results["distances"][0]
#             )):
#                 formatted_results.append({
#                     "text": doc,
#                     "metadata": metadata,
#                     "relevance_score": 1.0 - distance,  # Convert distance to similarity score
#                     "rank": i + 1
#                 })
            
#             logger.info(f"Hybrid search found {len(formatted_results)} relevant document chunks")
#         else:
#             logger.info("No relevant documents found")
            
#         return formatted_results
        
#     except Exception as e:
#         logger.error(f"Error in hybrid search: {str(e)}")
#         # Fall back to regular vector search
#         logger.info("Falling back to vector search")
#         return await query_documents(query_text, top_k=top_k, character_id=character_id)
def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF files"""
    logger.info(f"Extracting text from PDF: {file_path}")
    try:
        text = ""
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX files"""
    logger.info(f"Extracting text from DOCX: {file_path}")
    try:
        doc = docx.Document(file_path)
        text = "\n\n".join([paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()])
        return text
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {str(e)}")
        raise


def extract_text_from_doc(file_path: str) -> str:
    """Extract text from DOC files using mammoth"""
    logger.info(f"Extracting text from DOC: {file_path}")
    try:
        with open(file_path, "rb") as f:
            result = mammoth.extract_raw_text(f)
            return result.value
    except Exception as e:
        logger.error(f"Error extracting text from DOC: {str(e)}")
        raise


def extract_text_from_excel(file_path: str) -> str:
    """Extract text from Excel files"""
    logger.info(f"Extracting text from Excel: {file_path}")
    try:
        df = pd.read_excel(file_path)
        # Convert DataFrame to a readable string representation
        buffer = io.StringIO()
        df.to_csv(buffer)
        return buffer.getvalue()
    except Exception as e:
        logger.error(f"Error extracting text from Excel: {str(e)}")
        raise


def extract_text_from_csv(file_path: str) -> str:
    """Extract text from CSV files"""
    logger.info(f"Extracting text from CSV: {file_path}")
    try:
        # Use pandas for more robust CSV parsing
        df = pd.read_csv(file_path)
        # Convert DataFrame to a readable string representation
        buffer = io.StringIO()
        df.to_csv(buffer)
        return buffer.getvalue()
    except Exception as e:
        # Fallback to simple CSV reading if pandas fails
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                rows = list(reader)
                return "\n".join([",".join(row) for row in rows])
        except Exception as inner_e:
            logger.error(f"Error extracting text from CSV: {str(e)}, fallback also failed: {str(inner_e)}")
            raise e


def extract_text_from_text_file(file_path: str) -> str:
    """Extract text from text files"""
    logger.info(f"Extracting text from text file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error extracting text from text file: {str(e)}")
        raise

def scrape_with_requests(url: str) -> str:
    """Scrape content from a URL using requests"""
    logger.info(f"Scraping content with requests from: {url}")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "header", "footer", "nav"]):
            script.extract()
            
        # Extract text
        text = soup.get_text(separator='\n', strip=True)
        
        # Clean up text - remove excessive newlines and spaces
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    except Exception as e:
        logger.error(f"Error scraping with requests: {str(e)}")
        raise


async def scrape_with_playwright(url: str) -> str:
    """Scrape content from a URL using Playwright with enhanced content extraction logic"""
    logger.info(f"Scraping content with Playwright from: {url}")
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            
            page = await context.new_page()
            
            # Navigate with timeout and wait until network is idle
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for content to be fully loaded
            await page.wait_for_timeout(2000)
            
            # Get page title
            page_title = await page.title()
            
            # Special handling for tables
            table_content = ""
            if "daemon-ultimates" in url:
                logger.info("Detected Daemon Ultimates page with tables, using special extraction...")
                
                # Try to extract table content using JavaScript
                table_content = await page.evaluate("""() => {
                    const tables = document.querySelectorAll('[role="table"]');
                    let result = '';
                    
                    tables.forEach(table => {
                        // Get headers
                        const headers = Array.from(table.querySelectorAll('[role="columnheader"]'))
                            .map(header => header.textContent.trim());
                        
                        result += headers.join(' | ') + '\\n';
                        result += headers.map(() => '---').join(' | ') + '\\n';
                        
                        // Get rows - Include all rows, not just those after first child
                        const rows = table.querySelectorAll('[role="row"]');
                        // Skip the header row (first row)
                        for (let i = 1; i < rows.length; i++) {
                            const row = rows[i];
                            const cells = Array.from(row.querySelectorAll('[role="cell"]'))
                                .map(cell => cell.textContent.trim());
                            result += cells.join(' | ') + '\\n';
                        }
                        
                        result += '\\n\\n';
                    });
                    
                    return result;
                }""")
            
            # Extract simple content paragraphs
            simple_content = await page.evaluate("""() => {
                // Target the main content div and its paragraphs
                const contentDivs = document.querySelectorAll('div[class*="grid"]');
                let result = '';
                
                contentDivs.forEach(div => {
                    // Get all paragraphs inside this div
                    const paragraphs = div.querySelectorAll('p');
                    paragraphs.forEach(p => {
                        const text = p.textContent.trim();
                        if (text) {
                            result += text + '\\n\\n';
                        }
                    });
                });
                
                // Also try to get content from specific elements that might contain important text
                const headerText = document.querySelector('h1')?.textContent || '';
                const subheaderText = document.querySelector('header p')?.textContent || '';
                
                if (headerText) {
                    result = '# ' + headerText + '\\n\\n' + result;
                }
                
                if (subheaderText && subheaderText !== 'RESERVED') {
                    result = result + 'Note: ' + subheaderText + '\\n\\n';
                }
                
                return result;
            }""")
            
            # Extract content - try multiple selectors
            selectors = [
                "main", 
                "article", 
                ".content",
                ".prose",
                ".docusaurus-content",
                "[role='main']",
                ".container main",
                ".markdown",
                "table"
            ]
            
            content_html = None
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        content_html = await element.inner_html()
                        logger.info(f"Found content using selector: {selector}")
                        break
                except Exception as e:
                    continue
            
            # If no selector worked, capture the entire body content
            if not content_html:
                logger.info(f"No specific content container found for {url}, using body")
                body = await page.query_selector("body")
                if body:
                    content_html = await body.inner_html()
            
            # Process the content HTML if found
            structured_content = ""
            if content_html:
                from bs4 import BeautifulSoup
                
                # Use BeautifulSoup to parse the extracted HTML
                soup = BeautifulSoup(content_html, 'html.parser')
                
                # Find all headings to structure the content
                headings = soup.find_all(['h1', 'h2', 'h3'])
                
                # Process content by headings
                for i, heading in enumerate(headings):
                    # Get heading text
                    heading_text = heading.get_text(strip=True)
                    structured_content += f"# {heading_text}\n\n"
                    
                    # Find all elements between this heading and the next one
                    current = heading.next_sibling
                    
                    # Get next heading for boundary
                    next_heading = headings[i+1] if i < len(headings)-1 else None
                    
                    while current and (not next_heading or current != next_heading):
                        if current.name in ['p', 'ul', 'ol', 'pre', 'div', 'table', 'h4', 'h5', 'h6']:
                            content = current.get_text(strip=True)
                            if content:
                                structured_content += f"{content}\n\n"
                        current = current.next_sibling
                
                # If no structure was found, use a fallback approach
                if not structured_content:
                    # Extract all paragraphs and list items
                    paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]
                    list_items = []
                    for ul in soup.find_all(['ul', 'ol']):
                        for li in ul.find_all('li'):
                            text = li.get_text(strip=True)
                            if text:
                                list_items.append(f"• {text}")
                    
                    all_content = paragraphs + list_items
                    structured_content = "\n\n".join(all_content)
            
            # Combine all the extracted content
            final_content = ""
            
            # Add page title
            if page_title:
                final_content += f"# {page_title}\n\n"
            
            # Add simple content if available
            if simple_content:
                final_content += simple_content + "\n\n"
            
            # Add table content if available
            if table_content:
                final_content += f"## Tables\n\n{table_content}\n\n"
            
            # Add structured content if available
            if structured_content:
                final_content += structured_content
            
            # Close browser
            await browser.close()
            
            # Clean up the content
            final_content = final_content.strip()
            
            # If we have no content, try the original extraction method
            if not final_content:
                logger.info("No content found with enhanced methods, trying basic extraction")
                return await original_extraction(page)
            
            return final_content
            
    except Exception as e:
        logger.error(f"Error scraping with Playwright: {str(e)}")
        return ""  # Return empty string to allow fallback to requests

async def original_extraction(page):
    """Fall back to the original extraction method"""
    try:
        # Try to extract structured content
        content = await page.evaluate("""() => {
            // Try to get the main content
            const selectors = [
                "main", 
                "article", 
                ".content",
                ".prose",
                ".docusaurus-content",
                "[role='main']",
                ".container main",
                ".markdown"
            ];
            
            let mainContent = null;
            for (const selector of selectors) {
                const element = document.querySelector(selector);
                if (element) {
                    mainContent = element;
                    break;
                }
            }
            
            // If no main content container is found, use body
            const content = mainContent || document.body;
            
            // Remove unwanted elements
            const unwanted = content.querySelectorAll('nav, footer, header, script, style, [role="banner"], [role="navigation"]');
            unwanted.forEach(el => el.remove());
            
            // Extract text, preserving structure
            const extractText = (element) => {
                let result = '';
                
                // Handle headings
                if (['H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(element.tagName)) {
                    const level = element.tagName[1];
                    const prefix = '#'.repeat(parseInt(level)) + ' ';
                    return prefix + element.textContent.trim() + '\\n\\n';
                }
                
                // Handle paragraphs and other text elements
                if (['P', 'DIV', 'SPAN'].includes(element.tagName)) {
                    const text = element.textContent.trim();
                    if (text) return text + '\\n\\n';
                }
                
                // Handle lists
                if (element.tagName === 'LI') {
                    return '* ' + element.textContent.trim() + '\\n';
                }
                
                // Handle tables
                if (element.tagName === 'TABLE') {
                    let tableText = '\\n';
                    const rows = element.querySelectorAll('tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('th, td');
                        const rowText = Array.from(cells).map(cell => cell.textContent.trim()).join(' | ');
                        tableText += rowText + '\\n';
                    });
                    return tableText + '\\n';
                }
                
                // Process children recursively
                for (const child of element.childNodes) {
                    if (child.nodeType === Node.TEXT_NODE) {
                        const text = child.textContent.trim();
                        if (text) result += text + ' ';
                    } else if (child.nodeType === Node.ELEMENT_NODE) {
                        result += extractText(child);
                    }
                }
                
                return result;
            };
            
            return extractText(content);
        }""")
        
        return content.strip()
    except Exception as e:
        logger.error(f"Error with original extraction: {str(e)}")
        return ""

def chunk_text(text: str, title: str, doc_id: int, chunk_size: int = 1500, overlap: int = 200) -> List[Dict]:
    """Split text into overlapping chunks for embedding"""
    logger.info(f"Chunking text of length {len(text)} into chunks of size {chunk_size} with overlap {overlap}")
    
    chunks = []
    
    # If text is shorter than chunk_size, use it as a single chunk
    if len(text) <= chunk_size:
        chunks.append({
            "id": f"doc_{doc_id}_chunk_0",
            "text": text,
            "title": title,
            "doc_id": doc_id,
            "chunk_index": 0
        })
        return chunks
    
    # Otherwise, split into chunks with overlap
    current_idx = 0
    chunk_index = 0
    
    while current_idx < len(text):
        # Define chunk end (respect text boundaries)
        end_idx = min(current_idx + chunk_size, len(text))
        
        # Try to find a good breakpoint (newline or period)
        if end_idx < len(text):
            # Look for the last period or newline in the last 200 chars of the chunk
            last_period = text.rfind('.', current_idx, end_idx)
            last_newline = text.rfind('\n', current_idx, end_idx)
            
            breakpoint = max(last_period, last_newline)
            
            # Only use the breakpoint if it's not too far from the end
            if breakpoint > current_idx and (end_idx - breakpoint) < 200:
                end_idx = breakpoint + 1  # Include the period or newline
        
        # Create the chunk
        chunk_text = text[current_idx:end_idx].strip()
        
        if chunk_text:  # Only add non-empty chunks
            chunks.append({
                "id": f"doc_{doc_id}_chunk_{chunk_index}",
                "text": chunk_text,
                "title": f"{title} - Part {chunk_index + 1}",
                "doc_id": doc_id,
                "chunk_index": chunk_index
            })
            
            chunk_index += 1
        
        # Move to next chunk with overlap
        current_idx = end_idx - overlap if end_idx < len(text) else len(text)
        
        # Avoid getting stuck at the same position
        if current_idx <= 0:
            current_idx = end_idx
    
    logger.info(f"Created {len(chunks)} chunks from document")
    return chunks

# ... existing imports ...



async def create_embeddings(chunks: List[Dict], document: Document) -> None:
    """Create embeddings for text chunks and store them in ChromaDB"""
    logger.info(f"Creating embeddings for {len(chunks)} chunks")

    for i, chunk in enumerate(chunks):
        preview_text = chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"]
        logger.info(f"Chunk {i+1}/{len(chunks)} preview: {preview_text}")
    
    # Get or create collection
    try:
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Document embeddings for search"}
        )
    except Exception as e:
        logger.error(f"Error creating ChromaDB collection: {str(e)}")
        raise
    
    # Process chunks in batches to avoid rate limits
    batch_size = 10
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        
        # Extract data for embedding
        ids = [chunk["id"] for chunk in batch]
        texts = [chunk["text"] for chunk in batch]
        # Create metadata with URL for link documents
        metadatas = []
        for chunk in batch:
            metadata = {
                "title": chunk["title"],
                "doc_id": chunk["doc_id"],
                "chunk_index": chunk["chunk_index"],
                "document_title": document.title,
                "document_type": document.document_type.value,
                "original_filename": document.original_filename,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add URL to metadata if it's a link document
            if document.content_type == ContentType.LINK:
                metadata["url"] = document.file_path
                
            metadatas.append(metadata)
        
        try:
            # Create embeddings
            response = openai_client.embeddings.create(
                input=texts,
                model="text-embedding-3-large"  # Or your preferred embedding model
            )
            embeddings = [embedding.embedding for embedding in response.data]
            
            # Add to ChromaDB
            collection.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=texts
            )
            
            logger.info(f"Added batch of {len(batch)} embeddings to ChromaDB")
            
            # Rate limiting
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error creating embeddings: {str(e)}")
            raise