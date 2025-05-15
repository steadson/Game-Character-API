import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.document import Document, ContentType
from app.crud.documents import get_url_documents_for_refresh
from app.services.embedding import process_document
from app.core.config import settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

class DocumentRefreshScheduler:
    """Scheduler for refreshing URL documents at specified intervals."""
    
    def __init__(self):
        self.refresh_interval = None  # In hours
        self.is_running = False
        self.is_enabled = False
        self.processed_count = 0
        self.total_count = 0
        self.last_refresh_time = None
        self.task = None
    
    async def start(self, refresh_interval_hours: int):
        """Start the document refresh scheduler."""
        # if self.is_running:
        #     await self.stop()
        if self.task and not self.task.done():
            await self.stop()
        self.refresh_interval = refresh_interval_hours
        self.is_enabled = True
        self.is_running = True
        self.task = asyncio.create_task(self._refresh_loop())
        logger.info(f"Document refresh scheduler started with interval of {refresh_interval_hours} hours")
        return True
    
    async def stop(self):
        """Stop the document refresh scheduler."""
        # if self.is_running and self.task:
        #     self.is_running = False
        #     self.task.cancel()
        self.is_enabled = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            logger.info("Document refresh scheduler stopped")
    
    async def _refresh_loop(self):
        """Main refresh loop that runs at the specified interval."""
        #while self.is_running:
        while self.is_enabled:
            try:
                await self._refresh_documents()
            except Exception as e:
                logger.error(f"Error in document refresh loop: {str(e)}")
            
            # Sleep until next refresh interval
            await asyncio.sleep(self.refresh_interval * 3600)  # Convert hours to seconds
    
    async def _refresh_documents(self):
        """Refresh all URL documents in batches."""
        # Check if already running to prevent duplicate refreshes
        if self.is_running:
            logger.info("Document refresh already in progress. Skipping this request.")
            return
        logger.info("Starting scheduled document refresh")

        db = SessionLocal()
        try:
            # Get all URL documents that need refreshing
            documents = get_url_documents_for_refresh(db)
            total_docs = len(documents)
            logger.info(f"Found {total_docs} URL documents to refresh")
            
            # Set progress tracking variables
            self.processed_count = 0
            self.total_count = total_docs
            self.is_running = True
            
            # Process in batches of 5
            batch_size = 5
            for i in range(0, total_docs, batch_size):
                batch = documents[i:i+batch_size]
                logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} documents)")
                
                # Process each document in the batch
                for doc in batch:
                    try:
                        logger.info(f"Re-scraping and embedding document ID: {doc.id}, Title: {doc.title}")
                        await process_document(doc.id, db, reembed=True)
                        # Update last_refreshed timestamp
                        doc.last_refreshed = datetime.utcnow()
                        db.add(doc)
                        db.commit()
                        # Increment processed count after successful processing
                        self.processed_count += 1
                        logger.info(f"Progress: {self.processed_count}/{total_docs}")
                    except Exception as e:
                        logger.error(f"Error refreshing document ID {doc.id}: {str(e)}")
                        db.rollback()
                        # Still increment the count even if there was an error
                        self.processed_count += 1
                        logger.info(f"Progress (after error): {self.processed_count}/{total_docs}")
                
                # Small delay between batches to avoid overloading the system
                await asyncio.sleep(2)
            
            logger.info(f"Completed refreshing {total_docs} documents")
            self.is_running = False
            self.last_refresh_time = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error in document refresh process: {str(e)}")
            self.is_running = False
        finally:
            db.close()

# Create a global instance of the scheduler
document_scheduler = DocumentRefreshScheduler()

# async def initialize_scheduler():
#     """Initialize the document scheduler with default settings."""
#     # Default to 24 hours if not specified in settings
#     refresh_interval = getattr(settings, "DOCUMENT_REFRESH_INTERVAL_HOURS", 24)
#     await document_scheduler.start(refresh_interval)
# Update the existing initialize_scheduler function
async def initialize_scheduler():
    """Initialize and start the document refresh scheduler."""
    global document_scheduler
    
    # if document_scheduler is None:
    #     document_scheduler = DocumentRefreshScheduler()

    # Check if scheduler is already running to prevent duplicate tasks
    if document_scheduler.is_enabled and document_scheduler.task and not document_scheduler.task.done():
        logger.info("Document scheduler is already running. Skipping initialization.")
        return document_scheduler
    
    # Load settings from database or use defaults
    refresh_interval = 24  # Default to 24 hours
    
    # Start the scheduler with the configured interval
    await document_scheduler.start(refresh_interval)
    
    logger.info(f"Document refresh scheduler initialized and started with interval of {refresh_interval} hours")
    return document_scheduler
# Add this new function after the existing initialize_scheduler function
async def initialize_scheduler_without_autostart():
    """Initialize the document refresh scheduler without auto-starting it."""
    global document_scheduler
    
    # Create the scheduler if it doesn't exist
    if document_scheduler is None:
        document_scheduler = DocumentRefreshScheduler()

    
        
    # Set default refresh interval but don't start the scheduler
    document_scheduler.refresh_interval = 24  # Default to 24 hours
    document_scheduler.is_enabled = False  # Make sure it's disabled by default
    
    logger.info("Document refresh scheduler initialized in disabled state")
    return document_scheduler

async def update_refresh_interval(hours: int, enabled: bool = True):
    """Update the refresh interval and enable/disable the scheduler."""
    document_scheduler.refresh_interval = hours
    # Track the current state before making changes
    was_running = document_scheduler.is_running
    # Handle the enabled state
    #if enabled and not document_scheduler.is_running:
     # Handle the enabled state
    if enabled and not document_scheduler.is_enabled:
        # Start the scheduler if it should be enabled but isn't running
        await document_scheduler.start(hours)
        logger.info(f"Document scheduler started with interval of {hours} hours")
    elif not enabled and document_scheduler.is_enabled:
        # Stop the scheduler if it should be disabled but is running
        await document_scheduler.stop()
        logger.info("Document scheduler stopped")
    # Log the state change
    if was_running != document_scheduler.is_running:
        logger.info(f"Scheduler state changed from {was_running} to {document_scheduler.is_running}")
    return {
        "status": "success", 
        "message": f"Document refresh interval updated to {hours} hours. Auto-refresh is {'enabled' if enabled else 'disabled'}.",
        "hours": hours,
        "enabled": document_scheduler.is_enabled
    }