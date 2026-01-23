"""
Entity extraction service for NER and relationship mapping
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import uuid

import spacy
from spacy import displacy

from src.models.entity import Entity, EntityType, ExtractionMethod
from src.models.document import Document

logger = logging.getLogger(__name__)

class EntityExtractionService:
    """Service for extracting entities and relationships from text"""

    def __init__(self):
        """Initialize the entity extraction service"""
        self.nlp = None
        self.load_spacy_model()

    def load_spacy_model(self):
        """Load the spaCy language model"""
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("Successfully loaded spaCy model en_core_web_sm")
        except Exception as e:
            logger.error(f"Failed to load spaCy model: {str(e)}")
            raise

    def extract_entities_from_text(self, document: Document, text: str) -> List[Entity]:
        """Extract entities from text using spaCy NER and custom patterns"""
        if not self.nlp:
            logger.error("spaCy model not loaded")
            return []

        if not text or len(text.strip()) < 10:
            logger.warning("Text too short for entity extraction")
            return []

        entities = []

        # Process text with spaCy
        doc = self.nlp(text)

        # Extract named entities using spaCy
        for ent in doc.ents:
            entity = self._create_entity_from_spacy(document, ent)
            if entity:
                entities.append(entity)

        # Extract custom entities using regex patterns
        custom_entities = self._extract_custom_entities(document, text)
        entities.extend(custom_entities)

        # Extract relationships between entities
        relationships = self._extract_relationships(doc, entities)
        logger.info(f"Extracted {len(relationships)} relationships")

        # Deduplicate entities
        deduplicated_entities = self._deduplicate_entities(entities)

        logger.info(f"Extracted {len(deduplicated_entities)} unique entities from document")
        return deduplicated_entities

    def _create_entity_from_spacy(self, document: Document, spacy_entity) -> Optional[Entity]:
        """Create an Entity object from spaCy entity"""
        try:
            # Filter out low-quality entities early
            if not self._is_quality_entity(spacy_entity):
                return None

            # Map spaCy entity types to our entity types
            entity_type_mapping = {
                'PERSON': EntityType.PERSON,
                'ORG': EntityType.ORGANIZATION,
                'GPE': EntityType.LOCATION,  # Geopolitical Entity
                'LOC': EntityType.LOCATION,  # Location
                'PRODUCT': EntityType.PRODUCT,
                'EVENT': EntityType.CONCEPT,
                'WORK_OF_ART': EntityType.CONCEPT,
                'LAW': EntityType.CONCEPT,
                'LANGUAGE': EntityType.CONCEPT,
                'DATE': EntityType.DATE,
                'TIME': EntityType.DATE,
                'PERCENT': EntityType.NUMBER,
                'MONEY': EntityType.NUMBER,
                'QUANTITY': EntityType.NUMBER,
                'CARDINAL': EntityType.NUMBER,
                'ORDINAL': EntityType.NUMBER
            }

            spacy_type = spacy_entity.label_
            entity_type = entity_type_mapping.get(spacy_type, EntityType.CUSTOM)

            # Calculate confidence based on entity characteristics
            confidence = self._calculate_entity_confidence(spacy_entity)

            # Extract additional properties
            properties = {
                'spacy_label': spacy_type,
                'start_char': spacy_entity.start_char,
                'end_char': spacy_entity.end_char,
                'text_length': len(spacy_entity.text),
                'context_window': self._get_context_window(spacy_entity.sent, spacy_entity)
            }

            entity = Entity(
                entity_type=entity_type,
                name=spacy_entity.text.strip(),
                canonical_name=self._generate_canonical_name(spacy_entity.text, entity_type),
                confidence=confidence,
                extraction_method=ExtractionMethod.SPACY,
                extracted_at=datetime.now(),
                extraction_model="en_core_web_sm",
                properties=properties,
                document_id=document.id,
                organization_id=document.organization_id
            )

            return entity

        except Exception as e:
            logger.error(f"Error creating entity from spaCy: {str(e)}")
            return None

    def _extract_custom_entities(self, document: Document, text: str) -> List[Entity]:
        """Extract custom entities using regex patterns"""
        entities = []

        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        for match in re.finditer(email_pattern, text):
            entity = Entity(
                entity_type=EntityType.EMAIL,
                name=match.group(),
                confidence=0.95,
                extraction_method=ExtractionMethod.REGEX,
                extracted_at=datetime.now(),
                extraction_model="email_pattern",
                properties={'pattern': 'email_regex', 'start': match.start(), 'end': match.end()},
                document_id=document.id,
                organization_id=document.organization_id
            )
            entities.append(entity)

        # Phone numbers
        phone_pattern = r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'
        for match in re.finditer(phone_pattern, text):
            entity = Entity(
                entity_type=EntityType.PHONE,
                name=match.group(),
                confidence=0.90,
                extraction_method=ExtractionMethod.REGEX,
                extracted_at=datetime.now(),
                extraction_model="phone_pattern",
                properties={'pattern': 'phone_regex', 'start': match.start(), 'end': match.end()},
                document_id=document.id,
                organization_id=document.organization_id
            )
            entities.append(entity)

        # URLs
        url_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?'
        for match in re.finditer(url_pattern, text):
            entity = Entity(
                entity_type=EntityType.URL,
                name=match.group(),
                confidence=0.98,
                extraction_method=ExtractionMethod.REGEX,
                extracted_at=datetime.now(),
                extraction_model="url_pattern",
                properties={'pattern': 'url_regex', 'start': match.start(), 'end': match.end()},
                document_id=document.id,
                organization_id=document.organization_id
            )
            entities.append(entity)

        # Custom business entities (example: project codes, product names)
        # Project codes like PROJ-1234, PROD-5678
        project_pattern = r'\b(?:PROJ|PROD|TASK|TICKET)[-\s]?[0-9]{4,6}\b'
        for match in re.finditer(project_pattern, text, re.IGNORECASE):
            entity = Entity(
                entity_type=EntityType.CUSTOM,
                name=match.group(),
                canonical_name=match.group().upper(),
                confidence=0.85,
                extraction_method=ExtractionMethod.REGEX,
                extracted_at=datetime.now(),
                extraction_model="project_pattern",
                properties={
                    'pattern': 'project_regex',
                    'type': 'project_code',
                    'start': match.start(),
                    'end': match.end()
                },
                document_id=document.id,
                organization_id=document.organization_id
            )
            entities.append(entity)

        return entities

    def _extract_relationships(self, spacy_doc, entities: List[Entity]) -> List[Dict[str, Any]]:
        """Extract relationships between entities"""
        relationships = []

        # Simple relationship extraction based on dependency parsing
        for sent in spacy_doc.sents:
            sent_entities = [ent for ent in entities if
                           ent.properties and
                           'start_char' in ent.properties and
                           'end_char' in ent.properties and
                           ent.properties['start_char'] >= sent.start_char and
                           ent.properties['end_char'] <= sent.end_char]

            # Extract relationships based on dependency patterns
            if len(sent_entities) >= 2:
                for i, entity1 in enumerate(sent_entities):
                    for entity2 in sent_entities[i+1:]:
                        relationship = self._analyze_entity_relationship(sent, entity1, entity2)
                        if relationship:
                            relationships.append(relationship)

        return relationships

    def _analyze_entity_relationship(self, sentence, entity1: Entity, entity2: Entity) -> Optional[Dict[str, Any]]:
        """Analyze relationship between two entities in a sentence"""
        try:
            # Simple pattern-based relationship extraction
            # Look for relationship indicators between entities
            entity1_start = entity1.properties.get('start_char', 0) - sentence.start_char
            entity1_end = entity1.properties.get('end_char', 0) - sentence.start_char
            entity2_start = entity2.properties.get('start_char', 0) - sentence.start_char
            entity2_end = entity2.properties.get('end_char', 0) - sentence.start_char

            # Get text between entities
            if entity1_end < entity2_start:
                between_text = sentence.text[entity1_end:entity2_start].strip().lower()
            elif entity2_end < entity1_start:
                between_text = sentence.text[entity2_end:entity1_start].strip().lower()
            else:
                return None

            # Relationship patterns
            relationship_patterns = {
                'works_for': ['works at', 'works for', 'employed by', 'employee of'],
                'located_in': ['located in', 'based in', 'in', 'at'],
                'part_of': ['part of', 'member of', 'belongs to'],
                'related_to': ['related to', 'associated with', 'connected to'],
                'owns': ['owns', 'owner of', 'possesses'],
                'created_by': ['created by', 'made by', 'developed by'],
                'manages': ['manages', 'manager of', 'leads', 'supervises']
            }

            for relationship_type, patterns in relationship_patterns.items():
                for pattern in patterns:
                    if pattern in between_text:
                        return {
                            'source_entity': entity1,
                            'target_entity': entity2,
                            'relationship_type': relationship_type,
                            'confidence': 0.7,
                            'evidence': sentence.text,
                            'pattern_matched': pattern
                        }

            return None

        except Exception as e:
            logger.error(f"Error analyzing entity relationship: {str(e)}")
            return None

    def _calculate_entity_confidence(self, spacy_entity) -> float:
        """Calculate confidence score for spaCy entity"""
        base_confidence = 0.8

        # Adjust confidence based on entity characteristics
        text = spacy_entity.text.strip()

        # Length penalty/bonus
        if len(text) < 3:
            base_confidence -= 0.2
        elif len(text) > 20:
            base_confidence -= 0.1
        elif 5 <= len(text) <= 15:
            base_confidence += 0.1

        # Capitalization bonus for proper nouns
        if text and text[0].isupper():
            base_confidence += 0.1

        # Entity type-specific adjustments
        if spacy_entity.label_ in ['PERSON', 'ORG', 'GPE']:
            base_confidence += 0.1
        elif spacy_entity.label_ in ['DATE', 'TIME']:
            base_confidence += 0.15
        elif spacy_entity.label_ in ['CARDINAL', 'ORDINAL']:
            base_confidence -= 0.1

        return max(0.0, min(1.0, base_confidence))

    def _generate_canonical_name(self, text: str, entity_type: EntityType) -> str:
        """Generate canonical name for entity"""
        text = text.strip()

        if entity_type == EntityType.PERSON:
            # Simple name normalization
            parts = text.split()
            if len(parts) >= 2:
                # Last name, First name format
                return f"{parts[-1]}, {' '.join(parts[:-1])}"
            else:
                return text.title()

        elif entity_type == EntityType.ORGANIZATION:
            # Remove common suffixes and normalize
            suffixes = [' Inc.', ' Inc', ' LLC', ' Ltd.', ' Ltd', ' Corp.', ' Corp', ' Corporation']
            for suffix in suffixes:
                if text.endswith(suffix):
                    text = text[:-len(suffix)].strip()
            return text

        elif entity_type == EntityType.CUSTOM:
            # Uppercase for codes
            if re.match(r'^[A-Z]+[-\s]?[0-9]+$', text, re.IGNORECASE):
                return text.upper()

        return text

    def _get_context_window(self, sentence, entity, window_size: int = 50) -> str:
        """Get context window around entity"""
        entity_start = entity.start_char - sentence.start_char
        entity_end = entity.end_char - sentence.start_char

        start = max(0, entity_start - window_size)
        end = min(len(sentence.text), entity_end + window_size)

        return sentence.text[start:end]

    def _is_quality_entity(self, spacy_entity) -> bool:
        """Filter out low-quality entities that shouldn't be stored in knowledge graph"""
        text = spacy_entity.text.strip()
        entity_type = spacy_entity.label_

        # Whitelist of legitimate short names (universities, companies, acronyms)
        legitimate_short_names = {
            # Universities
            'MIT', 'UCLA', 'USC', 'NYU', 'UCL', 'ETH', 'EPFL', 'CMU', 'RIT',
            'Yale', 'Duke', 'Rice', 'Case', 'Drew',
            'GTech', 'GaTech', 'Caltech', 'Pitt',
            # Tech companies
            'IBM', 'SAP', 'AMD', 'ARM', 'AWS', 'GCP', 'API',
            'Meta', 'Uber', 'Lyft', 'Snap', 'Zoom',
            # Research/Standards
            'IEEE', 'ACM', 'ISO', 'NIST', 'DARPA', 'NASA', 'ESA',
            'WHO', 'FDA', 'CDC', 'NIH', 'NSF',
            # Common abbreviations
            'USA', 'UK', 'EU', 'UN', 'NATO', 'ASEAN',
            'CEO', 'CTO', 'CFO', 'COO', 'VP', 'SVP', 'EVP',
            'AI', 'ML', 'NLP', 'CV', 'IoT', 'API', 'GPU', 'CPU',
            'PhD', 'MSc', 'BSc', 'MBA', 'MD',
            # Cities with short names
            'LA', 'NY', 'SF', 'DC',
        }

        # Check if it's a known legitimate short name (case-insensitive)
        if text.upper() in legitimate_short_names:
            return True

        # Check if it looks like a legitimate abbreviation (all uppercase, 2-5 chars, alphabetic)
        if entity_type == 'ORG' and 2 <= len(text) <= 5:
            if text.isupper() and text.isalpha():
                # Likely a legitimate abbreviation
                return True

        # Skip entities that are too short
        if len(text) < 2:
            return False

        # Skip standalone numbers for CARDINAL/ORDINAL types
        if entity_type in ['CARDINAL', 'ORDINAL']:
            # Allow numbers only if they're part of meaningful context
            if text.isdigit() and len(text) <= 4:
                return False
            # Skip things like "l", "2)", "3.", etc.
            if re.match(r'^[\d\W]+$', text):
                return False

        # Skip meaningless single characters
        if len(text) == 1 and text.lower() in ['l', 'i', 'o', 'a', 's', 'x', 'y', 'z']:
            return False

        # Skip entities that are just punctuation or symbols
        if re.match(r'^[\W_]+$', text):
            return False

        # Skip entities that look like OCR errors (common in scanned documents)
        # e.g., "l20" (should be "120"), "l4" (should be "14")
        if re.match(r'^[l|I][0-9]+$', text, re.IGNORECASE):
            return False

        # Skip very short ORG entities (likely OCR errors) - but allow acronyms
        if entity_type == 'ORG' and len(text) <= 3:
            # Allow if it's all uppercase letters (likely acronym)
            if text.isupper() and text.isalpha():
                return True
            # Otherwise probably garbage
            return False

        # Skip very generic DATE entities
        if entity_type == 'DATE' and text.lower() in ['l', 'i', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
            return False

        # Skip NORP (nationalities/religious/political groups) that are too short
        if entity_type == 'NORP' and len(text) <= 2:
            return False

        # For PERSON entities, require at least 2 words or a longer single word
        if entity_type == 'PERSON':
            words = text.split()
            if len(words) == 1 and len(text) < 4:
                return False

        return True

    def _deduplicate_entities(self, entities: List[Entity]) -> List[Entity]:
        """Deduplicate entities based on name and type"""
        seen = set()
        deduplicated = []

        for entity in entities:
            # Create a key for deduplication
            canonical_name = entity.canonical_name or entity.name
            key = (entity.entity_type, canonical_name.lower().strip())

            if key not in seen:
                seen.add(key)
                deduplicated.append(entity)
            else:
                # Merge with existing entity if higher confidence
                existing_canonical = entity.canonical_name or entity.name
                existing_idx = next(i for i, e in enumerate(deduplicated)
                                 if (e.entity_type == entity.entity_type and
                                     (e.canonical_name or e.name).lower().strip() == existing_canonical.lower().strip()))

                if entity.confidence > deduplicated[existing_idx].confidence:
                    deduplicated[existing_idx] = entity

        return deduplicated

    def get_entity_statistics(self, entities: List[Entity]) -> Dict[str, Any]:
        """Get statistics about extracted entities"""
        stats = {
            'total_entities': len(entities),
            'entity_types': {},
            'extraction_methods': {},
            'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0},
            'average_confidence': 0.0
        }

        if not entities:
            return stats

        total_confidence = 0
        for entity in entities:
            # Count by type
            entity_type = entity.entity_type.value
            stats['entity_types'][entity_type] = stats['entity_types'].get(entity_type, 0) + 1

            # Count by extraction method
            method = entity.extraction_method.value
            stats['extraction_methods'][method] = stats['extraction_methods'].get(method, 0) + 1

            # Confidence distribution
            if entity.confidence >= 0.8:
                stats['confidence_distribution']['high'] += 1
            elif entity.confidence >= 0.6:
                stats['confidence_distribution']['medium'] += 1
            else:
                stats['confidence_distribution']['low'] += 1

            total_confidence += entity.confidence

        stats['average_confidence'] = total_confidence / len(entities)

        return stats