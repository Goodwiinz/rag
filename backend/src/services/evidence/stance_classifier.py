"""
Stance Classification Service for Evidence Agreement Meter

Classifies source stances on claims using LLM with structured output
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import openai
from pydantic import BaseModel, Field

from ...core.config import settings
from .cache import EvidenceCacheService

logger = logging.getLogger(__name__)


class StanceClassificationResult(BaseModel):
    """Result of stance classification"""
    stance: str
    confidence: float = Field(ge=0.0, le=1.0)
    justification_excerpt: str


class StanceClassifier:
    """Service for classifying source stances on claims using LLM"""
    
    def __init__(self, cache_service: Optional[EvidenceCacheService] = None):
        self.cache_service = cache_service
        self.model_version = "gpt-4o-mini-2024-07-18"
        self.fallback_model = "gpt-4o-2024-08-06"
        
    def _build_classification_prompt(self, claim: str, source_excerpt: str) -> str:
        """Build the prompt for stance classification"""
        return f"""You are an expert research analyst tasked with determining a source's stance on a specific claim.

CLAIM TO EVALUATE:
{claim}

SOURCE EXCERPT:
{source_excerpt}

CLASSIFICATION RULES:
- supporting: Source explicitly or implicitly agrees with the claim
- opposing: Source explicitly or implicitly disagrees with the claim  
- neutral: Source discusses the topic but takes no clear position on the claim
- not_addressed: Source doesn't relate to or address the claim

INSTRUCTIONS:
1. Analyze how the source excerpt relates to the specific claim
2. Determine the source's stance using the rules above
3. Provide a confidence score (0.0-1.0) based on how clear the stance is
4. Extract the most relevant excerpt (max 200 chars) that justifies your classification

Respond with ONLY a valid JSON object in this exact format:
{{"stance": "supporting|opposing|neutral|not_addressed", "confidence": 0.85, "justification_excerpt": "relevant text excerpt"}}"""

    async def _classify_with_openai(
        self, claim: str, source_excerpt: str, model: str, timeout: float = 15.0
    ) -> Optional[StanceClassificationResult]:
        """Classify stance using OpenAI API with JSON mode"""
        try:
            if not settings.OPENAI_API_KEY:
                logger.warning("OpenAI API key not configured")
                return None
                
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            
            prompt = self._build_classification_prompt(claim, source_excerpt)
            
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a research analyst. Respond only with valid JSON.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    max_tokens=300,
                    temperature=0.1,  # Low temperature for consistency
                    response_format={"type": "json_object"},  # Enforce JSON output
                ),
                timeout=timeout,
            )
            
            if not response.choices or not response.choices[0].message.content:
                logger.warning(f"OpenAI returned empty response for model {model}")
                return None
            
            result_json = response.choices[0].message.content.strip()
            result_data = json.loads(result_json)
            
            # Validate required fields
            required_fields = ["stance", "confidence", "justification_excerpt"]
            for field in required_fields:
                if field not in result_data:
                    logger.warning(f"Missing required field {field} in OpenAI response")
                    return None
            
            # Validate stance value
            valid_stances = ["supporting", "opposing", "neutral", "not_addressed"]
            if result_data["stance"] not in valid_stances:
                logger.warning(f"Invalid stance value: {result_data['stance']}")
                return None
                
            # Validate confidence range
            confidence = float(result_data["confidence"])
            if not (0.0 <= confidence <= 1.0):
                logger.warning(f"Invalid confidence value: {confidence}")
                return None
            
            # Truncate justification if too long
            justification = str(result_data["justification_excerpt"])[:200]
            
            return StanceClassificationResult(
                stance=result_data["stance"],
                confidence=confidence,
                justification_excerpt=justification
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from {model}: {e}")
            return None
        except asyncio.TimeoutError:
            logger.warning(f"Classification timed out for model {model}")
            return None
        except Exception as e:
            logger.error(f"Classification failed with {model}: {e}")
            return None
    
    async def _classify_with_fallback(
        self, claim: str, source_excerpt: str
    ) -> Optional[StanceClassificationResult]:
        """Classify with primary model, fallback to better model if confidence is low"""
        
        # Try primary model first
        result = await self._classify_with_openai(claim, source_excerpt, self.model_version)
        
        # If confidence is low, retry with better model
        if result and result.confidence < 0.85:
            logger.info(f"Low confidence ({result.confidence:.2f}), trying fallback model")
            fallback_result = await self._classify_with_openai(
                claim, source_excerpt, self.fallback_model, timeout=20.0
            )
            
            # Use fallback result if it has higher confidence
            if fallback_result and fallback_result.confidence > result.confidence:
                logger.info(f"Fallback model improved confidence: {result.confidence:.2f} -> {fallback_result.confidence:.2f}")
                return fallback_result
        
        return result
    
    def _generate_cache_key(self, claim_hash: str, source_id: str, excerpt_hash: str) -> str:
        """Generate cache key for stance classification"""
        return f"stance:{claim_hash}:{source_id}:{excerpt_hash}:{self.model_version}"
    
    async def classify_stance(
        self, claim: str, claim_hash: str, source_id: UUID, source_excerpt: str
    ) -> Optional[Dict]:
        """
        Classify a single source's stance on a claim
        
        Args:
            claim: The claim text
            claim_hash: SHA256 hash of normalized claim
            source_id: UUID of the source
            source_excerpt: Relevant text excerpt from source
            
        Returns:
            Classification result dict or None if failed
        """
        
        # Generate excerpt hash for caching
        excerpt_hash = str(hash(source_excerpt))[:16]
        cache_key = self._generate_cache_key(claim_hash, str(source_id), excerpt_hash)
        
        # Check cache first
        if self.cache_service:
            cached_result = await self.cache_service.get_stance_classification(cache_key)
            if cached_result:
                logger.debug(f"Using cached classification for source {source_id}")
                return cached_result
        
        # Classify with LLM
        try:
            result = await self._classify_with_fallback(claim, source_excerpt)
            
            if not result:
                logger.error(f"Failed to classify stance for source {source_id}")
                return None
            
            # Convert to dict for storage/caching
            result_dict = {
                "source_id": str(source_id),
                "stance": result.stance,
                "confidence": result.confidence,
                "justification_excerpt": result.justification_excerpt,
                "model_version": self.model_version,
            }
            
            # Cache result
            if self.cache_service:
                await self.cache_service.set_stance_classification(
                    cache_key, result_dict, ttl=86400  # 24 hours
                )
            
            logger.info(f"Classified source {source_id}: {result.stance} (confidence: {result.confidence:.2f})")
            return result_dict
            
        except Exception as e:
            logger.error(f"Unexpected error classifying source {source_id}: {e}")
            return None
    
    async def classify_sources_batch(
        self, claim: str, claim_hash: str, sources: List[Dict]
    ) -> List[Optional[Dict]]:
        """
        Classify multiple sources in parallel
        
        Args:
            claim: The claim text
            claim_hash: SHA256 hash of normalized claim  
            sources: List of dicts with 'source_id' and 'excerpt' keys
            
        Returns:
            List of classification results (None for failed classifications)
        """
        
        tasks = []
        for source in sources:
            task = self.classify_stance(
                claim=claim,
                claim_hash=claim_hash,
                source_id=source["source_id"], 
                source_excerpt=source["excerpt"]
            )
            tasks.append(task)
        
        # Run classifications in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Classification failed for source {sources[i]['source_id']}: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        success_count = sum(1 for r in processed_results if r is not None)
        logger.info(f"Batch classification completed: {success_count}/{len(sources)} successful")
        
        return processed_results