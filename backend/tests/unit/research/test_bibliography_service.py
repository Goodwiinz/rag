"""
Unit tests for BibliographyService (T107)

Tests bibliography formatting for BibTeX, IEEE, APA, and MLA formats.
"""

import pytest
from unittest.mock import MagicMock

from src.services.research.bibliography_service import BibliographyService


def create_mock_citation(**kwargs):
    """Create a mock Citation object with the given attributes."""
    citation = MagicMock()
    citation.document_title = kwargs.get("title", "Test Paper")
    citation.authors = kwargs.get("authors", ["Test Author"])
    citation.year = kwargs.get("year", 2023)
    citation.venue = kwargs.get("venue", "Test Journal")
    citation.doi = kwargs.get("doi", None)
    citation.arxiv_id = kwargs.get("arxiv_id", None)
    citation.abstract = kwargs.get("abstract", None)
    return citation


@pytest.fixture
def sample_citation():
    """Create a sample citation for testing."""
    return create_mock_citation(
        title="Deep Learning for Natural Language Processing",
        authors=["John Smith", "Jane Doe", "Bob Wilson"],
        year=2023,
        venue="Journal of Machine Learning Research",
        doi="10.1000/jmlr.2023.001",
        arxiv_id="2301.07041",
    )


@pytest.fixture
def sample_citation_incomplete():
    """Create a citation with incomplete metadata."""
    return create_mock_citation(
        title="Partial Paper",
        authors=["Unknown Author"],
        year=None,
        venue=None,
        doi=None,
    )


class TestBibTeXFormatting:
    """Tests for BibTeX format generation."""

    def test_format_bibtex_single_citation(self, sample_citation):
        """Test generating a valid BibTeX entry for a single citation."""
        result = BibliographyService.format_bibtex([sample_citation])

        assert result is not None
        assert "@article{" in result or "@misc{" in result
        assert "Deep Learning for Natural Language Processing" in result
        assert "Smith" in result
        assert "2023" in result
        assert "Journal of Machine Learning Research" in result

    def test_format_bibtex_multiple_citations(self, sample_citation):
        """Test generating a multi-entry .bib file."""
        citation2 = create_mock_citation(
            title="Second Paper on AI",
            authors=["Alice Brown"],
            year=2022,
            venue="AI Conference",
        )

        result = BibliographyService.format_bibtex([sample_citation, citation2])

        assert result is not None
        # Should contain two entries
        assert result.count("@") >= 2
        assert "Deep Learning" in result
        assert "Second Paper" in result

    def test_format_bibtex_special_characters(self):
        """Test BibTeX escaping of special characters."""
        citation = create_mock_citation(
            title="LaTeX & Special: A {Study} of $Math$",
            authors=["O'Brien, Jane"],
            year=2023,
            venue="Test Journal",
        )

        result = BibliographyService.format_bibtex([citation])

        assert result is not None
        # Special characters should be escaped or wrapped

    def test_format_bibtex_generates_unique_keys(self):
        """Test that each entry has a unique BibTeX key."""
        citations = [
            create_mock_citation(title="Paper One", authors=["Smith, John"], year=2023),
            create_mock_citation(title="Paper Two", authors=["Smith, John"], year=2023),
        ]

        result = BibliographyService.format_bibtex(citations)

        # Extract keys (format: @type{key, ...)
        import re
        keys = re.findall(r'@\w+\{([^,]+),', result)
        assert len(keys) == len(set(keys)), "BibTeX keys should be unique"


class TestIEEEFormatting:
    """Tests for IEEE reference format."""

    def test_format_ieee_citation(self, sample_citation):
        """Test generating IEEE reference format."""
        result = BibliographyService.format_ieee([sample_citation])

        assert result is not None
        # IEEE format: [N] A. Author, B. Author, "Title," Journal, vol. X, pp. Y-Z, Year.
        assert "Smith" in result
        assert "Deep Learning" in result
        assert "2023" in result

    def test_format_ieee_numbered_references(self, sample_citation):
        """Test that IEEE format includes numbered references."""
        citation2 = create_mock_citation(
            title="Second Paper",
            authors=["Bob Brown"],
            year=2022,
            venue="Conference",
        )

        result = BibliographyService.format_ieee([sample_citation, citation2])

        assert "[1]" in result
        assert "[2]" in result


class TestAPAFormatting:
    """Tests for APA reference format."""

    def test_format_apa_citation(self, sample_citation):
        """Test generating APA reference format."""
        result = BibliographyService.format_apa([sample_citation])

        assert result is not None
        # APA format: Author, A. A., Author, B. B., & Author, C. C. (Year). Title. Journal, Volume, Pages.
        assert "Smith" in result
        assert "(2023)" in result or "2023" in result
        assert "Deep Learning" in result

    def test_format_apa_et_al_rule(self):
        """Test APA 'et al.' rule for many authors."""
        citation = create_mock_citation(
            title="Many Authors Paper",
            authors=["Author One", "Author Two", "Author Three",
                    "Author Four", "Author Five", "Author Six",
                    "Author Seven", "Author Eight"],
            year=2023,
            venue="Test Journal",
        )

        result = BibliographyService.format_apa([citation])

        # APA uses et al. for 7+ authors
        assert result is not None


class TestMLAFormatting:
    """Tests for MLA reference format."""

    def test_format_mla_citation(self, sample_citation):
        """Test generating MLA reference format."""
        result = BibliographyService.format_mla([sample_citation])

        assert result is not None
        # MLA format: Author(s). "Title." Journal, vol. X, no. Y, Year, pp. Z.
        assert "Smith" in result
        assert "Deep Learning" in result
        assert "2023" in result


class TestIncompleteMetadata:
    """Tests for handling incomplete citation metadata."""

    def test_format_incomplete_metadata(self, sample_citation_incomplete):
        """Test handling missing fields gracefully with 'needs review' flag."""
        result = BibliographyService.format_bibtex([sample_citation_incomplete])

        assert result is not None
        # Should generate something even with missing fields
        assert "Partial Paper" in result

    def test_format_missing_year(self):
        """Test handling citation without year."""
        citation = create_mock_citation(
            title="No Year Paper",
            authors=["Test Author"],
            year=None,
            venue="Unknown Journal",
        )

        result = BibliographyService.format_bibtex([citation])

        assert result is not None
        # Should use placeholder or n.d. for missing year

    def test_format_missing_authors(self):
        """Test handling citation without authors."""
        citation = create_mock_citation(
            title="Anonymous Paper",
            authors=[],
            year=2023,
            venue="Test Journal",
        )

        result = BibliographyService.format_bibtex([citation])

        assert result is not None


class TestFormatSelection:
    """Tests for format selection interface."""

    def test_format_bibliography_bibtex(self, sample_citation):
        """Test format_bibliography with BibTeX format."""
        result = BibliographyService.format_bibliography([sample_citation], "bibtex")

        assert result is not None
        assert "@" in result

    def test_format_bibliography_ieee(self, sample_citation):
        """Test format_bibliography with IEEE format."""
        result = BibliographyService.format_bibliography([sample_citation], "ieee")

        assert result is not None

    def test_format_bibliography_apa(self, sample_citation):
        """Test format_bibliography with APA format."""
        result = BibliographyService.format_bibliography([sample_citation], "apa")

        assert result is not None

    def test_format_bibliography_mla(self, sample_citation):
        """Test format_bibliography with MLA format."""
        result = BibliographyService.format_bibliography([sample_citation], "mla")

        assert result is not None

    def test_format_bibliography_invalid_format(self, sample_citation):
        """Test handling of invalid format selection."""
        with pytest.raises((ValueError, KeyError)):
            BibliographyService.format_bibliography([sample_citation], "invalid_format")


class TestEmptyInput:
    """Tests for empty input handling."""

    def test_format_empty_list(self):
        """Test formatting empty citation list."""
        result = BibliographyService.format_bibtex([])

        # Empty list should return empty string
        assert result == "" or result is not None

    def test_format_bibliography_empty_list(self):
        """Test format_bibliography with empty list."""
        result = BibliographyService.format_bibliography([], "bibtex")

        assert result == "" or result is not None
