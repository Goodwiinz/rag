import sys
import os
from sqlalchemy import create_engine

# Add backend directory to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from src.core.database import Base, engine

# Import all models to ensure they are registered with Base
from src.models.user import User
from src.models.thread import Thread
from src.models.chat_message import ChatMessage
from src.models.conversation import Conversation
from src.models.workspace import Workspace
from src.models.collection import Collection
from src.models.document import Document
from src.models.citation import Citation
# Add other models as needed


def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


if __name__ == "__main__":
    init_db()
