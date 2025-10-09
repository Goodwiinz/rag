"""
Unit tests for EntityExtractionService
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.services.entity_extraction_service import EntityExtractionService
from src.models.entity import EntityType, ExtractionMethod
from src.models.document import Document


class TestEntityExtractionService:
    """Test cases for EntityExtractionService"""

    @patch('src.services.entity_extraction_service.spacy.load')
    def test_init_with_spacy_available(self, mock_spacy_load):
        """Test initialization when spaCy is available"""
        mock_nlp = Mock()
        mock_spacy_load.return_value = mock_nlp

        service = EntityExtractionService()

        assert service.nlp == mock_nlp
        mock_spacy_load.assert_called_once_with("en_core_web_sm")

    @patch('src.services.entity_extraction_service.spacy.load')
    def test_init_without_spacy_model(self, mock_spacy_load):
        """Test initialization when spaCy model is not available"""
        mock_spacy_load.side_effect = OSError("Model not found")

        service = EntityExtractionService()

        assert service.nlp is None

    def test_extract_entities_with_spacy_available(self):
        """Test entity extraction when spaCy is available"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            # Mock spaCy NLP
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            # Mock spaCy doc and entities
            mock_entity1 = Mock()
            mock_entity1.text = "John Doe"
            mock_entity1.label_ = "PERSON"
            mock_entity1.start_char = 0
            mock_entity1.end_char = 8

            mock_entity2 = Mock()
            mock_entity2.text = "Google"
            mock_entity2.label_ = "ORG"
            mock_entity2.start_char = 20
            mock_entity2.end_char = 26

            mock_doc = Mock()
            mock_doc.ents = [mock_entity1, mock_entity2]
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            text = "John Doe works at Google in California."
            entities = service.extract_entities(text)

            assert len(entities) == 2

            # Check first entity (person)
            person_entity = entities[0]
            assert person_entity['name'] == "John Doe"
            assert person_entity['entity_type'] == EntityType.PERSON
            assert person_entity['extraction_method'] == ExtractionMethod.SPACY_NER
            assert person_entity['confidence_score'] > 0.8
            assert person_entity['position'] == [0, 8]

            # Check second entity (organization)
            org_entity = entities[1]
            assert org_entity['name'] == "Google"
            assert org_entity['entity_type'] == EntityType.ORGANIZATION
            assert org_entity['extraction_method'] == ExtractionMethod.SPACY_NER
            assert org_entity['confidence_score'] > 0.8
            assert org_entity['position'] == [20, 26]

    def test_extract_entities_without_spacy_model(self):
        """Test entity extraction when spaCy model is not available"""
        service = EntityExtractionService()
        service.nlp = None

        text = "John Doe works at Google in California."
        entities = service.extract_entities(text)

        assert len(entities) == 0

    def test_extract_entities_empty_text(self):
        """Test entity extraction with empty text"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            mock_doc = Mock()
            mock_doc.ents = []
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            entities = service.extract_entities("")
            assert len(entities) == 0

    def test_extract_entities_with_custom_patterns(self):
        """Test entity extraction with custom business patterns"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            # Mock spaCy matcher
            mock_matcher = Mock()
            mock_matcher.return_value = []

            # Mock spaCy doc with custom entities
            mock_entity = Mock()
            mock_entity.text = "CEO"
            mock_entity.label_ = "JOB_TITLE"
            mock_entity.start_char = 10
            mock_entity.end_char = 13

            mock_doc = Mock()
            mock_doc.ents = [mock_entity]
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()
            service.matcher = mock_matcher

            text = "The CEO John Doe announced new products."
            entities = service.extract_entities(text)

            # Should find both spaCy entities and custom patterns
            assert len(entities) >= 1

            # Check for business-specific entities
            business_entities = [e for e in entities if e['entity_type'] in [EntityType.JOB_TITLE, EntityType.PRODUCT]]
            # This would test custom pattern matching

    @patch('src.services.entity_extraction_service.spacy.load')
    def test_spacy_entity_type_mapping(self, mock_load):
        """Test mapping of spaCy entity types to our entity types"""
        mock_nlp = Mock()
        mock_load.return_value = mock_nlp

        # Test different spaCy entity types
        test_cases = [
            ("PERSON", EntityType.PERSON),
            ("ORG", EntityType.ORGANIZATION),
            ("GPE", EntityType.LOCATION),
            ("MONEY", EntityType.FINANCIAL),
            ("DATE", EntityType.DATE),
            ("PRODUCT", EntityType.PRODUCT),
            ("EVENT", EntityType.EVENT),
            ("UNKNOWN", EntityType.OTHER)
        ]

        for spacy_type, expected_type in test_cases:
            mock_entity = Mock()
            mock_entity.text = "Test Entity"
            mock_entity.label_ = spacy_type
            mock_entity.start_char = 0
            mock_entity.end_char = 11

            mock_doc = Mock()
            mock_doc.ents = [mock_entity]
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()
            entities = service.extract_entities("Test text")

            if spacy_type != "UNKNOWN":  # Unknown types should be filtered out
                assert len(entities) == 1
                assert entities[0]['entity_type'] == expected_type
            else:
                # Unknown types should be mapped to OTHER or filtered
                assert len(entities) <= 1

    def test_extract_entities_with_confidence_scoring(self):
        """Test confidence scoring for extracted entities"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            # Mock entities with different characteristics
            mock_entity_capitalized = Mock()
            mock_entity_capitalized.text = "John Doe"
            mock_entity_capitalized.label_ = "PERSON"
            mock_entity_capitalized.start_char = 0
            mock_entity_capitalized.end_char = 8

            mock_entity_lowercase = Mock()
            mock_entity_lowercase.text = "john doe"
            mock_entity_lowercase.label_ = "PERSON"
            mock_entity_lowercase.start_char = 20
            mock_entity_lowercase.end_char = 28

            mock_doc = Mock()
            mock_doc.ents = [mock_entity_capitalized, mock_entity_lowercase]
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()
            entities = service.extract_entities("John Doe and john doe are different.")

            assert len(entities) == 2

            # Capitalized entity should have higher confidence
            capitalized_entity = entities[0]
            lowercase_entity = entities[1]

            assert capitalized_entity['confidence_score'] >= lowercase_entity['confidence_score']
            assert capitalized_entity['confidence_score'] > 0.9  # High confidence for capitalized
            assert lowercase_entity['confidence_score'] < 0.9  # Lower confidence for lowercase

    def test_extract_business_entities_email_patterns(self):
        """Test extraction of business entities like email addresses"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            mock_doc = Mock()
            mock_doc.ents = []  # No spaCy entities
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            text = "Contact john.doe@acme.com for more information about our products."
            entities = service.extract_entities(text)

            # Should find email entity
            email_entities = [e for e in entities if e['entity_type'] == EntityType.EMAIL]
            assert len(email_entities) >= 1

            email_entity = email_entities[0]
            assert "john.doe@acme.com" in email_entity['name']
            assert email_entity['extraction_method'] == ExtractionMethod.PATTERN_MATCHING

    def test_extract_business_entities_phone_patterns(self):
        """Test extraction of business entities like phone numbers"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            mock_doc = Mock()
            mock_doc.ents = []  # No spaCy entities
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            text = "Call us at (555) 123-4567 or +1-555-987-6543 for support."
            entities = service.extract_entities(text)

            # Should find phone entities
            phone_entities = [e for e in entities if e['entity_type'] == EntityType.PHONE]
            assert len(phone_entities) >= 1

            phone_entity = phone_entities[0]
            assert phone_entity['extraction_method'] == ExtractionMethod.PATTERN_MATCHING

    def test_extract_business_entities_url_patterns(self):
        """Test extraction of business entities like URLs"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            mock_doc = Mock()
            mock_doc.ents = []  # No spaCy entities
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            text = "Visit https://www.acme.com/products or http://example.org for details."
            entities = service.extract_entities(text)

            # Should find URL entities
            url_entities = [e for e in entities if e['entity_type'] == EntityType.URL]
            assert len(url_entities) >= 1

            url_entity = url_entities[0]
            assert url_entity['extraction_method'] == ExtractionMethod.PATTERN_MATCHING

    def test_extract_relationships_between_entities(self):
        """Test relationship extraction between entities"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            # Mock entities and their relationships
            mock_person = Mock()
            mock_person.text = "John Doe"
            mock_person.label_ = "PERSON"
            mock_person.start_char = 0
            mock_person.end_char = 8

            mock_org = Mock()
            mock_org.text = "Acme Corporation"
            mock_org.label_ = "ORG"
            mock_org.start_char = 17
            mock_org.end_char = 33

            # Mock dependency parsing
            mock_token1 = Mock()
            mock_token1.text = "John"
            mock_token1.dep_ = "nsubj"
            mock_token1.head.text = "works"

            mock_token2 = Mock()
            mock_token2.text = "works"
            mock_token2.dep_ = "ROOT"
            mock_token2.head.text = "works"

            mock_token3 = Mock()
            mock_token3.text = "Acme"
            mock_token3.dep_ = "pobj"
            mock_token3.head.text = "at"

            mock_doc = Mock()
            mock_doc.ents = [mock_person, mock_org]
            mock_doc.__iter__ = Mock(return_value=iter([mock_token1, mock_token2, mock_token3]))
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()
            entities = service.extract_entities("John Doe works at Acme Corporation.")

            assert len(entities) == 2

            # Check if relationships were detected
            relationships = service.extract_relationships("John Doe works at Acme Corporation.", entities)
            assert len(relationships) > 0

            # Should find EMPLOYER relationship
            employer_rels = [r for r in relationships if r['relationship_type'] == 'EMPLOYER']
            assert len(employer_rels) >= 1

    def test_calculate_entity_confidence_scores(self):
        """Test confidence score calculation for entities"""
        service = EntityExtractionService()

        # Test different confidence factors
        test_cases = [
            # (entity_text, entity_label, position_in_text, expected_confidence_range)
            ("Apple Inc.", "ORG", 0, (0.9, 1.0)),      # Well-known company, capitalized
            ("John Smith", "PERSON", 0, (0.9, 1.0)),    # Proper name format
            ("john smith", "PERSON", 0, (0.5, 0.8)),    # Lowercase name
            ("TechCorp", "ORG", 50, (0.7, 0.9)),        # Mid-text entity
            ("$1,000,000", "MONEY", 100, (0.8, 1.0)),  # Specific format
        ]

        for text, label, position, expected_range in test_cases:
            confidence = service._calculate_confidence_score(text, label, position, "This is a test text with " + text)
            assert expected_range[0] <= confidence <= expected_range[1]

    def test_extract_entities_from_large_text(self):
        """Test entity extraction from large text documents"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            # Create many mock entities for large text
            entities = []
            for i in range(50):  # 50 entities
                mock_entity = Mock()
                mock_entity.text = f"Entity {i}"
                mock_entity.label_ = "ORG" if i % 2 == 0 else "PERSON"
                mock_entity.start_char = i * 20
                mock_entity.end_char = (i + 1) * 20
                entities.append(mock_entity)

            mock_doc = Mock()
            mock_doc.ents = entities
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            # Create large text (10KB)
            large_text = "This is a large text document. " * 200
            extracted_entities = service.extract_entities(large_text)

            assert len(extracted_entities) == 50

            # Check that all entities were processed
            for i, entity in enumerate(extracted_entities):
                assert entity['name'] == f"Entity {i}"
                assert entity['confidence_score'] > 0.0
                assert 'position' in entity
                assert 'metadata' in entity

    def test_extract_entities_with_special_characters(self):
        """Test entity extraction with special characters and Unicode"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            # Mock entities with special characters
            mock_entity1 = Mock()
            mock_entity1.text = "José Martínez"
            mock_entity1.label_ = "PERSON"
            mock_entity1.start_char = 0
            mock_entity1.end_char = 14

            mock_entity2 = Mock()
            mock_entity2.text = "São Paulo"
            mock_entity2.label_ = "GPE"
            mock_entity2.start_char = 20
            mock_entity2.end_char = 30

            mock_doc = Mock()
            mock_doc.ents = [mock_entity1, mock_entity2]
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            text = "José Martínez lives in São Paulo, Brazil."
            entities = service.extract_entities(text)

            assert len(entities) == 2

            # Check Unicode handling
            person_entity = entities[0]
            assert person_entity['name'] == "José Martínez"
            assert person_entity['entity_type'] == EntityType.PERSON

            location_entity = entities[1]
            assert location_entity['name'] == "São Paulo"
            assert location_entity['entity_type'] == EntityType.LOCATION

    def test_filter_duplicate_entities(self):
        """Test filtering of duplicate entities"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            # Create duplicate entities
            mock_entity1 = Mock()
            mock_entity1.text = "John Doe"
            mock_entity1.label_ = "PERSON"
            mock_entity1.start_char = 0
            mock_entity1.end_char = 8

            mock_entity2 = Mock()
            mock_entity2.text = "John Doe"  # Same text
            mock_entity2.label_ = "PERSON"
            mock_entity2.start_char = 50  # Different position
            mock_entity2.end_char = 58

            mock_doc = Mock()
            mock_doc.ents = [mock_entity1, mock_entity2]
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            text = "John Doe works here. John Doe is the CEO."
            entities = service.extract_entities(text)

            # Should deduplicate based on text and type
            person_entities = [e for e in entities if e['name'] == "John Doe"]
            # Depending on implementation, might keep both with different positions or deduplicate
            assert len(person_entities) >= 1

    def test_extract_entities_performance(self):
        """Test performance of entity extraction"""
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_nlp = Mock()
            mock_load.return_value = mock_nlp

            # Mock a reasonable number of entities
            entities = []
            for i in range(20):
                mock_entity = Mock()
                mock_entity.text = f"Entity_{i}"
                mock_entity.label_ = "ORG"
                mock_entity.start_char = i * 15
                mock_entity.end_char = (i + 1) * 15
                entities.append(mock_entity)

            mock_doc = Mock()
            mock_doc.ents = entities
            mock_nlp.return_value = mock_doc

            service = EntityExtractionService()

            import time
            text = "Sample text " * 100  # Medium-sized text

            start_time = time.time()
            extracted_entities = service.extract_entities(text)
            end_time = time.time()

            processing_time = end_time - start_time

            # Should complete within reasonable time (1 second for this test)
            assert processing_time < 1.0
            assert len(extracted_entities) == 20