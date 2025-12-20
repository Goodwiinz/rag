"""
Entity extraction service using LLM and NLP techniques
"""

import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.models.entity import EntityType, ExtractionMethod
from src.models.graph import RelationshipType
from src.core.config import settings
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class EntityExtractionService:
    """Service for extracting entities and relationships from text"""

    def __init__(self):
        # Initialize Azure OpenAI client for LLM extraction
        self.llm_client = None
        # Try RAG-specific config first (gpt-4o-mini), then fallback to chat config
        if (hasattr(settings, 'AZURE_OPENAI_RAG_API_KEY') and
            hasattr(settings, 'AZURE_OPENAI_RAG_ENDPOINT') and
            hasattr(settings, 'AZURE_OPENAI_RAG_DEPLOYMENT_NAME')):
            try:
                self.llm_client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_RAG_API_KEY,
                    azure_endpoint=settings.AZURE_OPENAI_RAG_ENDPOINT,
                    api_version=settings.AZURE_OPENAI_RAG_API_VERSION
                )
                self.llm_deployment_name = settings.AZURE_OPENAI_RAG_DEPLOYMENT_NAME
                logger.info(f"Initialized Azure OpenAI client with deployment: {settings.AZURE_OPENAI_RAG_DEPLOYMENT_NAME} (gpt-4o-mini)")
            except Exception as e:
                logger.error(f"Failed to initialize Azure OpenAI RAG client: {e}")
                self.llm_client = None
        elif (settings.AZURE_OPENAI_CHAT_API_KEY and
              settings.AZURE_OPENAI_CHAT_ENDPOINT and
              settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME):
            try:
                self.llm_client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_CHAT_API_KEY,
                    azure_endpoint=settings.AZURE_OPENAI_CHAT_ENDPOINT,
                    api_version=settings.AZURE_OPENAI_CHAT_API_VERSION
                )
                self.llm_deployment_name = settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
                logger.info(f"Initialized Azure OpenAI client with deployment: {settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME}")
            except Exception as e:
                logger.error(f"Failed to initialize Azure OpenAI chat client: {e}")
                self.llm_client = None
        else:
            logger.info("Azure OpenAI credentials not configured. LLM extraction will be disabled.")

        # Predefined patterns for common entity types
        self.patterns = {
            EntityType.EMAIL: re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            EntityType.PHONE: re.compile(r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'),
            EntityType.URL: re.compile(r'\bhttps?:\/\/(?:[-\w.])+(?:[:\d]+)?(?:\/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?\b'),
            EntityType.DATE: re.compile(r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b|\b\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}\b'),
            # EntityType.NUMBER covers financial numbers
            "NUMBER": re.compile(r'\$\d+(?:,\d{3})*(?:\.\d{2})?|\$\d+\.\d{2}|\b\d+(?:,\d{3})*\s*(?:USD|EUR|GBP|CAD|AUD)\b'),
        }

        # Common relationship indicators
        self.relationship_indicators = {
            RelationshipType.WORKS_FOR: ['works for', 'employed by', 'employee of', 'works at'],
            RelationshipType.KNOWS: ['knows', 'knowing', 'knowing about', 'acquaintance of'],
            RelationshipType.RELATED_TO: ['related to', 'associated with', 'connected to', 'linked to'],
            RelationshipType.LOCATED_IN: ['located in', 'based in', 'in', 'at', 'office in'],
            RelationshipType.PART_OF: ['part of', 'member of', 'division of', 'subdivision of'],
            RelationshipType.MANAGES: ['manages', 'managed by', 'supervises', 'supervised by'],
            RelationshipType.COLLABORATES_WITH: ['collaborates with', 'works with', 'partnered with', 'teams with'],
            RelationshipType.REPORTS_TO: ['reports to', 'supervised by', 'answerable to'],
            RelationshipType.MEMBER_OF: ['member of', 'belongs to', 'joined', 'participates in'],
            RelationshipType.ATTENDED: ['attended', 'went to', 'participated in', 'visited'],
        }

        # Common organization indicators
        self.org_indicators = ['Inc', 'Corp', 'LLC', 'Ltd', 'Company', 'Corporation', 'Institute', 'University', 'College', 'Hospital', 'Bank', 'Agency', 'Department']

        # Common person title indicators
        self.title_indicators = ['Mr', 'Mrs', 'Ms', 'Dr', 'Prof', 'CEO', 'CTO', 'CFO', 'President', 'Director', 'Manager', 'Vice President', 'VP']

    async def extract_entities(self, text: str, document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract entities and relationships from text"""
        try:
            # Extract entities using multiple methods
            entities = []

            # Pattern-based extraction
            pattern_entities = await self._extract_with_patterns(text)
            entities.extend(pattern_entities)

            # Rule-based extraction
            rule_entities = await self._extract_with_rules(text)
            entities.extend(rule_entities)

            # LLM-based extraction (if available)
            try:
                llm_entities = await self._extract_with_llm(text)
                entities.extend(llm_entities)
            except Exception as e:
                logger.warning(f"LLM extraction failed: {e}")

            # Deduplicate entities
            deduplicated_entities = await self._deduplicate_entities(entities)

            # Extract relationships
            relationships = await self._extract_relationships(text, deduplicated_entities)

            # Combine entities and relationships
            result = []

            for entity in deduplicated_entities:
                result.append({
                    "name": entity["name"],
                    "entity_type": entity["entity_type"],
                    "confidence_score": entity["confidence_score"],
                    "extraction_method": entity["extraction_method"],
                    "position": entity.get("position"),
                    "context": entity.get("context"),
                    "metadata": entity.get("metadata", {}),
                    "source_document_id": document_id
                })

            for relationship in relationships:
                result.append({
                    "source_entity_id": relationship["source_entity_id"],
                    "target_entity_id": relationship["target_entity_id"],
                    "relationship_type": relationship["relationship_type"],
                    "strength": relationship["strength"],
                    "confidence_score": relationship["confidence_score"],
                    "context": relationship.get("context"),
                    "evidence": relationship.get("evidence", []),
                    "metadata": relationship.get("metadata", {}),
                    "source_document_id": document_id
                })

            return result

        except Exception as e:
            logger.error(f"Error extracting entities from text: {e}")
            return []

    async def _extract_with_patterns(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using regex patterns"""
        entities = []

        for entity_type, pattern in self.patterns.items():
            matches = pattern.finditer(text)
            for match in matches:
                # Get context around the match
                start_pos = max(0, match.start() - 50)
                end_pos = min(len(text), match.end() + 50)
                context = text[start_pos:end_pos].strip()

                entities.append({
                    "name": match.group(),
                    "entity_type": entity_type.value,
                    "confidence_score": 0.9,  # High confidence for pattern matches
                    "extraction_method": ExtractionMethod.REGEX.value,  # Using REGEX for pattern matching
                    "position": [match.start(), match.end()],
                    "context": context,
                    "metadata": {
                        "extraction_method": "regex_pattern",
                        "pattern_used": pattern.pattern
                    }
                })

        return entities

    async def _extract_with_rules(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using rule-based heuristics"""
        entities = []

        # Extract organizations
        org_entities = await self._extract_organizations(text)
        entities.extend(org_entities)

        # Extract persons
        person_entities = await self._extract_persons(text)
        entities.extend(person_entities)

        # Extract locations
        location_entities = await self._extract_locations(text)
        entities.extend(location_entities)

        # Extract job titles
        title_entities = await self._extract_job_titles(text)
        entities.extend(title_entities)

        return entities

    async def _extract_organizations(self, text: str) -> List[Dict[str, Any]]:
        """Extract organization names"""
        entities = []

        # Look for capitalized words followed by organization indicators
        words = text.split()
        for i, word in enumerate(words):
            # Check if word might be an organization
            if (word[0].isupper() and
                any(indicator.lower() in word.lower() for indicator in self.org_indicators)):

                # Get context
                start_pos = text.find(word)
                if start_pos != -1:
                    context_start = max(0, start_pos - 50)
                    context_end = min(len(text), start_pos + len(word) + 50)
                    context = text[context_start:context_end].strip()

                    entities.append({
                        "name": word,
                        "entity_type": EntityType.ORGANIZATION.value,
                        "confidence_score": 0.8,
                        "extraction_method": "rule_based",  # String value for rule-based extraction
                        "position": [start_pos, start_pos + len(word)],
                        "context": context,
                        "metadata": {
                            "extraction_rule": "organization_indicator",
                            "indicator_found": [ind for ind in self.org_indicators if ind.lower() in word.lower()]
                        }
                    })

        return entities

    async def _extract_persons(self, text: str) -> List[Dict[str, Any]]:
        """Extract person names"""
        entities = []

        # Simple rule: Look for title + name patterns
        for title in self.title_indicators:
            title_pattern = rf'{title}\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
            matches = re.finditer(title_pattern, text, re.IGNORECASE)

            for match in matches:
                name = match.group(1)
                start_pos = match.start()

                # Get context
                context_start = max(0, start_pos - 50)
                context_end = min(len(text), start_pos + len(match.group()) + 50)
                context = text[context_start:context_end].strip()

                entities.append({
                    "name": name,
                    "entity_type": EntityType.PERSON.value,
                    "confidence_score": 0.85,
                    "extraction_method": "rule_based",  # String value for rule-based extraction
                    "position": [start_pos + len(title) + 1, start_pos + len(match.group())],
                    "context": context,
                    "metadata": {
                        "extraction_rule": "title_name_pattern",
                        "title": title
                    }
                })

        return entities

    async def _extract_locations(self, text: str) -> List[Dict[str, Any]]:
        """Extract location names"""
        entities = []

        # Simple patterns for locations (this would be enhanced with a proper NER model)
        location_patterns = [
            r'\b[A-Z][a-z]+,\s*[A-Z]{2}\b',  # City, State
            r'\b[A-Z][a-z]+,\s*[A-Z][a-z]+\b',  # City, Country
            r'\b[0-9]+\s+[A-Z][a-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b'
        ]

        for pattern in location_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                start_pos = match.start()

                # Get context
                context_start = max(0, start_pos - 50)
                context_end = min(len(text), start_pos + len(match.group()) + 50)
                context = text[context_start:context_end].strip()

                entities.append({
                    "name": match.group(),
                    "entity_type": EntityType.LOCATION.value,
                    "confidence_score": 0.8,
                    "extraction_method": "rule_based",  # String value for rule-based extraction
                    "position": [start_pos, start_pos + len(match.group())],
                    "context": context,
                    "metadata": {
                        "extraction_rule": "location_pattern",
                        "pattern": pattern
                    }
                })

        return entities

    async def _extract_job_titles(self, text: str) -> List[Dict[str, Any]]:
        """Extract job titles"""
        entities = []

        # Look for job titles in text
        title_words = [
            'Engineer', 'Manager', 'Director', 'Developer', 'Analyst', 'Consultant',
            'Specialist', 'Coordinator', 'Administrator', 'Assistant', 'Associate',
            'Senior', 'Lead', 'Principal', 'Chief', 'Head', 'President', 'Vice President'
        ]

        for title_word in title_words:
            # Look for capitalized title words
            pattern = rf'\b[A-Z][a-z]*\s+{title_word}\b'
            matches = re.finditer(pattern, text)

            for match in matches:
                start_pos = match.start()

                # Get context
                context_start = max(0, start_pos - 50)
                context_end = min(len(text), start_pos + len(match.group()) + 50)
                context = text[context_start:context_end].strip()

                entities.append({
                    "name": match.group(),
                    "entity_type": EntityType.CUSTOM.value,  # Using CUSTOM for job titles
                    "confidence_score": 0.75,
                    "extraction_method": "rule_based",  # String value for rule-based extraction
                    "position": [start_pos, start_pos + len(match.group())],
                    "context": context,
                    "metadata": {
                        "extraction_rule": "job_title_pattern",
                        "title_keyword": title_word
                    }
                })

        return entities

    async def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using Azure OpenAI LLM"""
        if not self.llm_client:
            logger.warning("LLM client not available for entity extraction")
            return []

        try:
            # Truncate text if too long (leave room for prompt and response)
            max_text_length = 8000  # Adjust based on model's context limit
            truncated_text = text[:max_text_length] if len(text) > max_text_length else text

            # Create prompt for entity extraction
            prompt = f"""Extract entities and relationships from the following text.
Return a JSON object with the following structure:

{{
    "entities": [
        {{
            "name": "Entity Name",
            "entity_type": "PERSON|ORGANIZATION|LOCATION|PRODUCT|CONCEPT|DATE|NUMBER|EMAIL|PHONE|URL|CUSTOM",
            "confidence_score": 0.0-1.0,
            "position": [start_index, end_index],
            "context": "relevant text snippet",
            "metadata": {{
                "description": "Brief description of the entity",
                "aliases": ["alternative names"]
            }}
        }}
    ],
    "relationships": [
        {{
            "source_entity": "Source Entity Name",
            "target_entity": "Target Entity Name",
            "relationship_type": "WORKS_FOR|KNOWS|RELATED_TO|LOCATED_IN|PART_OF|MANAGES|COLLABORATES_WITH|REPORTS_TO|MEMBER_OF|ATTENDED|CREATED|OWNS|USES|REFERENCES",
            "confidence_score": 0.0-1.0,
            "context": "text describing the relationship",
            "evidence": ["supporting quotes"]
        }}
    ]
}}

Text to analyze:
{truncated_text}

Focus on:
1. Named entities (people, organizations, locations)
2. Specific concepts and technologies
3. Relationships between entities
4. Provide confidence scores based on how certain you are

JSON Response:"""

            # Call Azure OpenAI
            response = self.llm_client.chat.completions.create(
                model=self.llm_deployment_name,
                messages=[
                    {"role": "system", "content": "You are an expert at entity extraction and relationship analysis. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            # Parse the response
            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from LLM")
                return []

            result = json.loads(content)
            entities = []

            # Convert entities to our format
            for entity in result.get("entities", []):
                entities.append({
                    "name": entity["name"],
                    "entity_type": self._normalize_entity_type(entity["entity_type"]),
                    "confidence_score": min(1.0, max(0.0, float(entity.get("confidence_score", 0.7)))),
                    "extraction_method": ExtractionMethod.OPENAI.value,  # Using OPENAI enum for LLM extraction
                    "position": entity.get("position"),
                    "context": entity.get("context", ""),
                    "metadata": {
                        "extraction_method": "llm_azure_openai",
                        "model": self.llm_deployment_name,
                        "description": entity.get("metadata", {}).get("description", ""),
                        "aliases": entity.get("metadata", {}).get("aliases", [])
                    }
                })

            # Convert relationships to our format (these will be processed separately)
            # For now, we'll only return entities from LLM extraction to keep the flow simple
            # Relationships will be extracted by the main relationship extraction method

            logger.info(f"Extracted {len(entities)} entities using LLM")
            return entities

        except Exception as e:
            logger.error(f"Error in LLM entity extraction: {e}")
            return []

    def _normalize_entity_type(self, llm_type: str) -> str:
        """Normalize entity types from LLM to our enum values"""
        type_mapping = {
            "PERSON": EntityType.PERSON.value,
            "ORGANIZATION": EntityType.ORGANIZATION.value,
            "LOCATION": EntityType.LOCATION.value,
            "PRODUCT": EntityType.PRODUCT.value,
            "CONCEPT": EntityType.CONCEPT.value,
            "DATE": EntityType.DATE.value,
            "NUMBER": EntityType.NUMBER.value,
            "EMAIL": EntityType.EMAIL.value,
            "PHONE": EntityType.PHONE.value,
            "URL": EntityType.URL.value,
            "CUSTOM": EntityType.CUSTOM.value,
            "EVENT": EntityType.CONCEPT.value,  # Map EVENT to CONCEPT
            "TECHNOLOGY": EntityType.CONCEPT.value,  # Map TECHNOLOGY to CONCEPT
            "JOB_TITLE": EntityType.CUSTOM.value,  # Map JOB_TITLE to CUSTOM
            "FINANCIAL": EntityType.NUMBER.value,  # Map FINANCIAL to NUMBER
        }

        return type_mapping.get(llm_type.upper(), EntityType.CONCEPT.value)

    async def _extract_relationships(self, text: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relationships between entities"""
        relationships = []

        # Look for relationship indicators in text
        for rel_type, indicators in self.relationship_indicators.items():
            for indicator in indicators:
                # Find sentences containing relationship indicators
                sentences = re.split(r'[.!?]+', text)

                for sentence in sentences:
                    if indicator.lower() in sentence.lower():
                        # Find entities mentioned in this sentence
                        sentence_entities = []
                        for entity in entities:
                            entity_name = entity["name"]
                            if entity_name.lower() in sentence.lower():
                                sentence_entities.append(entity)

                        # Create relationships between entities in the same sentence
                        if len(sentence_entities) >= 2:
                            for i in range(len(sentence_entities)):
                                for j in range(i + 1, len(sentence_entities)):
                                    # Determine relationship strength based on proximity
                                    entity1_pos = sentence.lower().find(sentence_entities[i]["name"].lower())
                                    entity2_pos = sentence.lower().find(sentence_entities[j]["name"].lower())
                                    distance = abs(entity1_pos - entity2_pos)

                                    # Closer entities have stronger relationships
                                    strength = max(0.1, 1.0 - (distance / len(sentence)))

                                    relationships.append({
                                        "source_entity_id": sentence_entities[i]["name"],  # Would be actual ID in real implementation
                                        "target_entity_id": sentence_entities[j]["name"],  # Would be actual ID in real implementation
                                        "relationship_type": rel_type.value,
                                        "strength": strength,
                                        "confidence_score": 0.7,
                                        "context": sentence.strip(),
                                        "evidence": [sentence.strip()],
                                        "metadata": {
                                            "extraction_method": "rule_based",
                                            "relationship_indicator": indicator,
                                            "sentence_distance": distance
                                        }
                                    })

        return relationships

    async def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate entities and merge information"""
        seen_entities = {}
        deduplicated = []

        for entity in entities:
            key = (entity["name"].lower(), entity["entity_type"])

            if key not in seen_entities:
                seen_entities[key] = entity
                deduplicated.append(entity)
            else:
                # Merge with existing entity
                existing = seen_entities[key]

                # Keep higher confidence score
                if entity["confidence_score"] > existing["confidence_score"]:
                    existing["confidence_score"] = entity["confidence_score"]

                # Merge extraction methods
                if entity["extraction_method"] not in existing.get("metadata", {}).get("extraction_methods", []):
                    existing["metadata"] = existing.get("metadata", {})
                    existing["metadata"]["extraction_methods"] = existing["metadata"].get("extraction_methods", [])
                    existing["metadata"]["extraction_methods"].append(entity["extraction_method"])

        return deduplicated