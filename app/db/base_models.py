# Import all models here for Alembic to detect
from app.db.base import Base
from app.models.user import User
from app.models.admin_secret import AdminSecret
# Import other existing models
# Add the new Conversation model
from app.models.conversation import Conversation