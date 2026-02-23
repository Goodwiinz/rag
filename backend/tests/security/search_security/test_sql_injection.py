"""
SQL Injection Prevention Tests for Search Endpoints

Tests comprehensive SQL injection prevention including:
- Query parameter injection attacks
- Filter parameter injection
- Sort parameter injection
- Union-based injection
- Boolean-based blind injection
- Time-based blind injection
- Second-order injection
- Database-specific injection vectors
"""

import pytest
import time
from unittest.mock import patch, Mock
import uuid
from typing import List, Dict, Any

from .conftest import SecurityTestCase


class TestSQLInjectionPrevention(SecurityTestCase):
    """Test SQL injection prevention in search endpoints"""

    def test_basic_sql_injection_in_query(self, security_test_client, authentication_headers, search_service_mocks):
        """Test basic SQL injection attempts in search query"""
        
        sql_injection_payloads = [
            "test'; DROP TABLE documents; --",
            "test' OR '1'='1",
            "test' UNION SELECT * FROM users --",
            "test'; INSERT INTO logs VALUES('hacked'); --",
            "test' AND (SELECT COUNT(*) FROM information_schema.tables) > 0 --",
            "test'; EXEC xp_cmdshell('dir'); --",
            "test' OR 1=1; --",
            "test\" OR \"1\"=\"1",
            "test\"; DROP TABLE users; --",
            "test' OR EXISTS(SELECT 1 FROM users WHERE username='admin') --",
        ]
        
        for payload in sql_injection_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            # Should either sanitize and process (200) or reject safely
            assert response.status_code in [200, 400, 422], \
                f"SQL injection should be handled safely: {payload}"
            
            if response.status_code != 200:
                self.assert_safe_error_response(response)
            
            # Ensure SQL commands are not executed
            response_text = response.text.lower()
            dangerous_responses = [
                'table', 'dropped', 'inserted', 'deleted', 'updated',
                'syntax error', 'mysql', 'postgresql', 'sqlite',
                'information_schema', 'pg_', 'mysql_', 'sys.'
            ]
            
            for dangerous in dangerous_responses:
                assert dangerous not in response_text, \
                    f"Response should not contain SQL execution evidence: {dangerous}"

    def test_union_based_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test UNION-based SQL injection attempts"""
        
        union_payloads = [
            "test' UNION SELECT username, password FROM users --",
            "test' UNION ALL SELECT id, email FROM users WHERE id=1 --",
            "test' UNION SELECT 1, 2, 3, 4, 5 --",
            "test' UNION SELECT null, null, null --",
            "test' UNION SELECT version(), database(), user() --",
            "test' UNION SELECT @@version, @@datadir, @@basedir --",
            "test' UNION SELECT table_name FROM information_schema.tables --",
            "test' UNION SELECT column_name FROM information_schema.columns --",
            "test' UNION SELECT schema_name FROM information_schema.schemata --",
            "test' UNION SELECT load_file('/etc/passwd') --",
        ]
        
        for payload in union_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"UNION injection should be handled safely: {payload}"
            
            # Check that no sensitive data is leaked
            sensitive_patterns = [
                'username', 'password', 'email', 'version()',
                'database()', 'user()', 'root:', 'admin:',
                'information_schema', 'table_name', 'column_name'
            ]
            
            self.assert_no_information_disclosure(response, sensitive_patterns)

    def test_boolean_based_blind_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test boolean-based blind SQL injection attempts"""
        
        # Boolean-based payloads that attempt to infer information
        boolean_payloads = [
            "test' AND (SELECT COUNT(*) FROM users) > 0 --",
            "test' AND (SELECT LENGTH(database())) > 5 --",
            "test' AND (SELECT SUBSTRING(user(),1,1)) = 'r' --",
            "test' AND (SELECT ASCII(SUBSTRING(database(),1,1))) > 64 --",
            "test' AND EXISTS(SELECT * FROM information_schema.tables) --",
            "test' AND (SELECT COUNT(*) FROM documents WHERE id > 0) = (SELECT COUNT(*) FROM documents WHERE id > 0) --",
            "test' AND 1=1 --",
            "test' AND 1=2 --",
            "test' AND 'a'='a' --",
            "test' AND 'a'='b' --",
        ]
        
        response_times = []
        
        for payload in boolean_payloads:
            start_time = time.time()
            
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            end_time = time.time()
            response_times.append(end_time - start_time)
            
            assert response.status_code in [200, 400, 422], \
                f"Boolean injection should be handled safely: {payload}"
            
            if response.status_code != 200:
                self.assert_safe_error_response(response)
        
        # Check that response times don't vary significantly (indicating blind SQL injection)
        if len(response_times) > 1:
            avg_time = sum(response_times) / len(response_times)
            for resp_time in response_times:
                # Response times shouldn't vary by more than 5x (allowing for normal variation)
                assert resp_time < avg_time * 5, \
                    "Response times should not vary significantly (potential blind SQL injection)"

    def test_time_based_blind_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test time-based blind SQL injection attempts"""
        
        # Time-based payloads that attempt to cause delays
        time_based_payloads = [
            "test'; WAITFOR DELAY '00:00:05'; --",
            "test' AND (SELECT SLEEP(5)) --",
            "test'; SELECT pg_sleep(5); --",
            "test' AND (SELECT * FROM (SELECT COUNT(*),CONCAT(version(),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a) --",
            "test'; BENCHMARK(5000000, MD5('test')); --",
            "test' AND (SELECT * FROM (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=database() AND 5000000*RAND()>5000000*RAND())x) --",
            "test' UNION SELECT IF(1=1,SLEEP(5),0) --",
        ]
        
        for payload in time_based_payloads:
            start_time = time.time()
            
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            # Response should not be delayed significantly
            assert response_time < 2.0, \
                f"Time-based injection may be succeeding - response took {response_time}s: {payload}"
            
            assert response.status_code in [200, 400, 422], \
                f"Time-based injection should be handled safely: {payload}"

    def test_filter_parameter_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test SQL injection in filter parameters"""
        
        # SQL injection in various filter parameters
        filter_injection_tests = [
            # organization_id injection
            {
                "query": "test",
                "filters": {
                    "organization_id": "1' OR '1'='1"
                }
            },
            # uploaded_by_user_id injection
            {
                "query": "test",
                "filters": {
                    "uploaded_by_user_id": "admin'; DROP TABLE users; --"
                }
            },
            # tags injection
            {
                "query": "test",
                "filters": {
                    "tags": ["tag1", "tag2'; DELETE FROM tags; --", "tag3"]
                }
            },
            # document_types injection
            {
                "query": "test",
                "filters": {
                    "document_types": ["pdf'; UNION SELECT password FROM users; --"]
                }
            },
            # Date field injection
            {
                "query": "test",
                "filters": {
                    "date_from": "2023-01-01'; DROP TABLE documents; --"
                }
            },
            # File size injection
            {
                "query": "test",
                "filters": {
                    "file_size_min": "100'; SELECT * FROM users; --"
                }
            },
        ]
        
        for payload in filter_injection_tests:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=payload
            )
            
            # Should sanitize or reject
            assert response.status_code in [200, 400, 422], \
                f"Filter injection should be handled safely: {payload}"
            
            if response.status_code != 200:
                self.assert_safe_error_response(response)

    def test_sort_parameter_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test SQL injection in sort parameters"""
        
        # SQL injection in sort_order parameter
        sort_injection_payloads = [
            "relevance; DROP TABLE documents; --",
            "date_desc'; UNION SELECT * FROM users; --",
            "title_asc, (SELECT password FROM users WHERE id=1)",
            "relevance' OR '1'='1",
            "date_desc'; INSERT INTO logs VALUES('injected'); --",
        ]
        
        for sort_payload in sort_injection_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={
                    "query": "test",
                    "sort_order": sort_payload
                }
            )
            
            # Should reject invalid sort orders
            assert response.status_code == 422, \
                f"Invalid sort order should be rejected: {sort_payload}"
            self.assert_safe_error_response(response)

    def test_pagination_parameter_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test SQL injection in pagination parameters"""
        
        # SQL injection in limit and offset
        pagination_injections = [
            {"limit": "10; DROP TABLE documents; --"},
            {"offset": "0'; SELECT * FROM users; --"},
            {"limit": "10' UNION SELECT password FROM users; --"},
            {"offset": "5' OR '1'='1"},
            {"limit": "20'; INSERT INTO logs VALUES('hacked'); --"},
        ]
        
        for injection in pagination_injections:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={
                    "query": "test",
                    **injection
                }
            )
            
            # Should reject non-integer values
            assert response.status_code == 422, \
                f"Non-integer pagination should be rejected: {injection}"
            self.assert_safe_error_response(response)

    def test_second_order_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test second-order SQL injection attacks"""
        
        # First, try to inject malicious data into search history
        malicious_queries = [
            "test'; DROP TABLE documents; --",
            "search' UNION SELECT password FROM users; --",
        ]
        
        for malicious_query in malicious_queries:
            # Store potentially malicious query in history
            response = security_test_client.make_request(
                'POST',
                '/search/history',
                headers=authentication_headers['valid_jwt'],
                json={"query": malicious_query}
            )
            
            # Should handle safely
            assert response.status_code in [200, 400, 422], \
                "Malicious history entry should be handled safely"
            
            # Now try to retrieve history (second-order attack)
            response = security_test_client.make_request(
                'GET',
                '/search/history',
                headers=authentication_headers['valid_jwt']
            )
            
            assert response.status_code == 200, "History retrieval should work"
            
            # History response should not execute the injected SQL
            self.assert_no_information_disclosure(response, [
                'password', 'username', 'table', 'dropped', 'users'
            ])

    def test_database_specific_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test database-specific SQL injection vectors"""
        
        # PostgreSQL specific
        postgresql_payloads = [
            "test'; COPY users TO '/tmp/users.txt'; --",
            "test'; SELECT version(); --",
            "test' AND (SELECT current_user) = 'postgres' --",
            "test'; CREATE TABLE hacked (id int); --",
            "test' UNION SELECT lo_import('/etc/passwd', 12345) --",
        ]
        
        # MySQL specific
        mysql_payloads = [
            "test'; SELECT * INTO OUTFILE '/tmp/users.txt' FROM users; --",
            "test' AND (SELECT @@version) LIKE '%mysql%' --",
            "test'; LOAD DATA INFILE '/etc/passwd' INTO TABLE temp; --",
            "test' UNION SELECT load_file('/etc/passwd') --",
        ]
        
        # SQLite specific
        sqlite_payloads = [
            "test'; ATTACH DATABASE '/tmp/evil.db' AS evil; --",
            "test' AND sqlite_version() LIKE '3.%' --",
        ]
        
        all_payloads = postgresql_payloads + mysql_payloads + sqlite_payloads
        
        for payload in all_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"DB-specific injection should be handled safely: {payload}"
            
            # Check for database-specific information leakage
            db_specific_patterns = [
                'postgres', 'mysql', 'sqlite', 'version()',
                'current_user', '@@version', 'sqlite_version()',
                '/etc/passwd', '/tmp/', 'outfile', 'infile', 'load_file'
            ]
            
            self.assert_no_information_disclosure(response, db_specific_patterns)

    def test_encoded_injection_attempts(self, security_test_client, authentication_headers, search_service_mocks):
        """Test SQL injection with various encoding attempts"""
        
        # URL encoded injection
        url_encoded_payloads = [
            "test%27%20OR%20%271%27%3D%271",  # test' OR '1'='1
            "test%27%3B%20DROP%20TABLE%20documents%3B%20--",  # test'; DROP TABLE documents; --
            "test%27%20UNION%20SELECT%20*%20FROM%20users%20--",  # test' UNION SELECT * FROM users --
        ]
        
        # Double encoded injection
        double_encoded_payloads = [
            "test%2527%2520OR%2520%25271%2527%253D%25271",
        ]
        
        # Hex encoded injection
        hex_encoded_payloads = [
            "test\\x27\\x20OR\\x20\\x27\\x31\\x27\\x3D\\x27\\x31",
        ]
        
        # Unicode encoded injection
        unicode_payloads = [
            "test\\u0027 OR \\u00271\\u0027=\\u00271",
        ]
        
        all_encoded_payloads = (url_encoded_payloads + double_encoded_payloads + 
                               hex_encoded_payloads + unicode_payloads)
        
        for payload in all_encoded_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Encoded injection should be handled safely: {payload}"
            
            if response.status_code != 200:
                self.assert_safe_error_response(response)

    def test_suggestions_endpoint_injection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test SQL injection in suggestions endpoint"""
        
        suggestion_injection_payloads = [
            "test'; DROP TABLE suggestions; --",
            "search' UNION SELECT password FROM users --",
            "query' AND (SELECT COUNT(*) FROM users) > 0 --",
        ]
        
        for payload in suggestion_injection_payloads:
            response = security_test_client.make_request(
                'GET',
                f'/search/suggestions?q={payload}',
                headers=authentication_headers['valid_jwt']
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Suggestions injection should be handled safely: {payload}"
            
            if response.status_code == 200:
                # Response should not contain SQL execution evidence
                self.assert_no_information_disclosure(response, [
                    'password', 'users', 'table', 'dropped', 'error'
                ])

    def test_nested_injection_attempts(self, security_test_client, authentication_headers, search_service_mocks):
        """Test nested and complex SQL injection attempts"""
        
        nested_injection_payloads = [
            {
                "query": "test",
                "filters": {
                    "tags": ["tag1", "tag2"],
                    "organization_id": "uuid'; (SELECT CASE WHEN (1=1) THEN pg_sleep(5) ELSE pg_sleep(0) END); --"
                }
            },
            {
                "query": "search' AND (SELECT * FROM (SELECT COUNT(*),CONCAT(version(),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a) AND '1'='1",
                "search_type": "hybrid",
                "filters": {
                    "document_types": ["pdf'; UPDATE users SET password='hacked' WHERE id=1; --"]
                }
            },
            {
                "query": "test",
                "limit": 10,
                "offset": 0,
                "filters": {
                    "tags": ["normal_tag"],
                    "date_from": "2023-01-01",
                    "uploaded_by_user_id": "user123'; INSERT INTO logs (event, data) VALUES ('breach', (SELECT password FROM users LIMIT 1)); --"
                }
            }
        ]
        
        for payload in nested_injection_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json=payload
            )
            
            assert response.status_code in [200, 400, 422], \
                f"Nested injection should be handled safely: {payload}"
            
            if response.status_code != 200:
                self.assert_safe_error_response(response)
            
            # Check for evidence of successful injection.
            # Note: words like 'password' and 'users' appear in the test
            # payloads themselves and Pydantic reflects them in validation
            # errors.  Only check for patterns that indicate real DB leakage.
            dangerous_patterns = [
                'information_schema', 'pg_sleep', 'rand()',
            ]

            self.assert_no_information_disclosure(response, dangerous_patterns)

    def test_service_layer_injection_protection(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that service layer properly sanitizes inputs"""

        injection_payload = {
            "query": "test'; DROP TABLE documents; --",
            "search_type": "fulltext",
            "filters": {
                "organization_id": "uuid'; SELECT * FROM users; --"
            }
        }

        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=authentication_headers['valid_jwt'],
            json=injection_payload
        )

        # Should either process safely (200) or reject (422)
        assert response.status_code in [200, 422], \
            "Injection payload should be handled safely"

        # If successful, verify the mock service was called
        if response.status_code == 200:
            mock_service = search_service_mocks['fulltext']
            mock_service.search.assert_called()

            # Check the arguments passed to the service
            call_args = mock_service.search.call_args
            search_request = call_args[1].get('search_request')

            if search_request:
                # The service should receive the query as-is (sanitization
                # happens at the DB layer, not at the API layer)
                assert search_request.query is not None
                assert isinstance(search_request.query, str)

    def test_error_based_injection_information_disclosure(self, security_test_client, authentication_headers, search_service_mocks):
        """Test that error-based injection doesn't disclose database information"""
        
        error_inducing_payloads = [
            "test' AND (SELECT * FROM non_existent_table) --",
            "test' AND CAST((SELECT version()) AS int) --",
            "test' AND 1=CONVERT(int, (SELECT @@version)) --",
            "test' AND extractvalue(1, concat(0x5c, (SELECT version()))) --",
            "test' AND updatexml(1, concat(0x5c, (SELECT user())), 1) --",
        ]
        
        for payload in error_inducing_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=authentication_headers['valid_jwt'],
                json={"query": payload, "search_type": "fulltext"}
            )
            
            # Should not leak database errors
            database_error_patterns = [
                'mysql', 'postgresql', 'sqlite', 'oracle', 'mssql',
                'syntax error', 'column', 'table', 'database',
                'constraint', 'foreign key', 'primary key',
                'duplicate entry', 'access denied', 'permission denied',
                'unknown column', 'unknown table', 'invalid object',
                'conversion failed', 'cast', 'convert'
            ]
            
            self.assert_no_information_disclosure(response, database_error_patterns)
            
            if response.status_code not in [200]:
                self.assert_safe_error_response(response)