# Import all models here for Alembic to detect
from app.db.base import Base
from app.models.user import User
# Import other existing models
# Add the new Conversation model
from app.models.conversation import Conversation