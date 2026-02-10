"""
Neo4j Cypher templates for Evidence Agreement Meter

Contains templates for creating Claim nodes and TAKES_STANCE relationships
"""

from typing import Dict, List, Any


class Neo4jTemplates:
    """Collection of Cypher templates for evidence meter Neo4j operations"""
    
    # Create or merge a Claim node
    CREATE_CLAIM_NODE = """
    MERGE (c:Claim {hash: $claim_hash})
    ON CREATE SET 
        c.text = $claim_text,
        c.normalized = $normalized_text,
        c.created_at = datetime(),
        c.updated_at = datetime()
    ON MATCH SET
        c.updated_at = datetime()
    RETURN c
    """
    
    # Create TAKES_STANCE relationship between Source and Claim
    CREATE_TAKES_STANCE = """
    MATCH (s:Source {id: $source_id})
    MERGE (c:Claim {hash: $claim_hash})
    ON CREATE SET 
        c.text = $claim_text,
        c.normalized = $normalized_text,
        c.created_at = datetime(),
        c.updated_at = datetime()
    MERGE (s)-[r:TAKES_STANCE {
        claim_hash: $claim_hash,
        model_version: $model_version
    }]->(c)
    ON CREATE SET
        r.stance = $stance,
        r.confidence = $confidence,
        r.justification_excerpt = $justification_excerpt,
        r.classified_at = datetime()
    ON MATCH SET
        r.stance = $stance,
        r.confidence = $confidence,
        r.justification_excerpt = $justification_excerpt,
        r.classified_at = datetime()
    RETURN r
    """
    
    # Get all sources that take a stance on a claim
    GET_CLAIM_STANCES = """
    MATCH (c:Claim {hash: $claim_hash})<-[r:TAKES_STANCE]-(s:Source)
    WHERE r.model_version = $model_version
    RETURN s.id as source_id, s.title as source_title, 
           r.stance as stance, r.confidence as confidence,
           r.justification_excerpt as justification_excerpt,
           r.classified_at as classified_at
    ORDER BY r.confidence DESC
    """
    
    # Get stances for specific sources and claim
    GET_SOURCES_STANCES = """
    MATCH (c:Claim {hash: $claim_hash})<-[r:TAKES_STANCE]-(s:Source)
    WHERE s.id IN $source_ids AND r.model_version = $model_version
    RETURN s.id as source_id, s.title as source_title,
           r.stance as stance, r.confidence as confidence, 
           r.justification_excerpt as justification_excerpt,
           r.classified_at as classified_at
    ORDER BY r.confidence DESC
    """
    
    # Find similar claims (for potential reuse)
    FIND_SIMILAR_CLAIMS = """
    MATCH (c:Claim)
    WHERE ANY(kw IN $normalized_keywords WHERE c.normalized CONTAINS kw)
    RETURN c.hash as claim_hash, c.text as claim_text, c.normalized as normalized_text
    LIMIT 10
    """
    
    # Get consensus statistics for a claim
    GET_CONSENSUS_STATS = """
    MATCH (c:Claim {hash: $claim_hash})<-[r:TAKES_STANCE]-(s:Source)
    WHERE r.model_version = $model_version
    WITH 
        count(CASE WHEN r.stance = 'supporting' THEN 1 END) as supporting,
        count(CASE WHEN r.stance = 'opposing' THEN 1 END) as opposing,
        count(CASE WHEN r.stance = 'neutral' THEN 1 END) as neutral,
        count(CASE WHEN r.stance = 'not_addressed' THEN 1 END) as not_addressed,
        avg(r.confidence) as avg_confidence,
        count(r) as total
    RETURN supporting, opposing, neutral, not_addressed, avg_confidence, total
    """
    
    # Get temporal analysis (evolution of consensus over time)
    GET_TEMPORAL_CONSENSUS = """
    MATCH (c:Claim {hash: $claim_hash})<-[r:TAKES_STANCE]-(s:Source)
    WHERE r.model_version = $model_version AND s.publication_date IS NOT NULL
    WITH s.publication_date.year as year, r.stance as stance
    ORDER BY year
    WITH year, 
         count(CASE WHEN stance = 'supporting' THEN 1 END) as supporting,
         count(CASE WHEN stance = 'opposing' THEN 1 END) as opposing,
         count(CASE WHEN stance = 'neutral' THEN 1 END) as neutral,
         count(*) as total
    RETURN year, supporting, opposing, neutral, total
    ORDER BY year
    """
    
    # Delete stances for outdated model versions
    DELETE_OUTDATED_STANCES = """
    MATCH ()-[r:TAKES_STANCE]->()
    WHERE r.model_version <> $current_model_version
    DELETE r
    """
    
    # Get retracted sources that have stances on a claim
    GET_RETRACTED_SOURCES_FOR_CLAIM = """
    MATCH (c:Claim {hash: $claim_hash})<-[r:TAKES_STANCE]-(s:Source)
    WHERE r.model_version = $model_version AND s.is_retracted = true
    RETURN s.id as source_id, s.title as source_title,
           r.stance as stance, r.confidence as confidence
    """

    @classmethod
    def build_create_claim_params(cls, claim_hash: str, claim_text: str, normalized_text: str) -> Dict[str, Any]:
        """Build parameters for CREATE_CLAIM_NODE template"""
        return {
            'claim_hash': claim_hash,
            'claim_text': claim_text,
            'normalized_text': normalized_text
        }
    
    @classmethod
    def build_stance_params(cls, source_id: str, claim_hash: str, claim_text: str, 
                           normalized_text: str, stance: str, confidence: float,
                           justification_excerpt: str, model_version: str) -> Dict[str, Any]:
        """Build parameters for CREATE_TAKES_STANCE template"""
        return {
            'source_id': source_id,
            'claim_hash': claim_hash,
            'claim_text': claim_text,
            'normalized_text': normalized_text,
            'stance': stance,
            'confidence': confidence,
            'justification_excerpt': justification_excerpt,
            'model_version': model_version
        }
    
    @classmethod
    def build_query_params(cls, claim_hash: str, model_version: str, 
                          source_ids: List[str] = None) -> Dict[str, Any]:
        """Build parameters for query templates"""
        params = {
            'claim_hash': claim_hash,
            'model_version': model_version
        }
        if source_ids:
            params['source_ids'] = source_ids
        return params
