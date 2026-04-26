"""
Add evidence meter and stance classifications tables
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.core.database import engine
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)


def run_migration():
    """Run the evidence meter migration"""
    logger.info("Starting evidence meter migration...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Create stance_classifications table
            logger.info("Creating stance_classifications table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS stance_classifications (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    claim_hash VARCHAR(64) NOT NULL,
                    source_id UUID NOT NULL,
                    stance VARCHAR(20) NOT NULL CHECK (stance IN ('supporting', 'opposing', 'neutral', 'not_addressed')),
                    confidence FLOAT NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
                    justification_excerpt TEXT,
                    model_version VARCHAR(50) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    
                    UNIQUE(claim_hash, source_id, model_version)
                )
            """))

            # Create indexes for stance_classifications
            logger.info("Creating indexes for stance_classifications...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_stance_claim 
                ON stance_classifications(claim_hash)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_stance_source 
                ON stance_classifications(source_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_stance_claim_model 
                ON stance_classifications(claim_hash, model_version)
            """))
            
            trans.commit()
            logger.info("Evidence meter migration completed successfully")
            
        except Exception as e:
            trans.rollback()
            logger.error(f"Migration failed: {e}")
            raise
            

def rollback_migration():
    """Rollback the evidence meter migration"""
    logger.info("Rolling back evidence meter migration...")
    
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("DROP TABLE IF EXISTS stance_classifications CASCADE"))
            trans.commit()
            logger.info("Evidence meter migration rolled back successfully")
        except Exception as e:
            trans.rollback()
            logger.error(f"Rollback failed: {e}")
            raise


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        run_migration()