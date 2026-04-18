"""
API Contract Testing Framework for Multimodal Enterprise RAG System

This module provides comprehensive API contract testing using OpenAPI 3.0 specifications.
It validates request/response schemas, status codes, headers, and ensures API compliance.
"""

import pytest
import json
import yaml
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from fastapi.testclient import TestClient
from pydantic import ValidationError
import requests
from urllib.parse import urljoin

from src.main import app


class APITestSpec:
    """Represents an API test specification from OpenAPI"""

    def __init__(self, path: str, method: str, operation_spec: Dict[str, Any],
                 path_parameters: Dict[str, Any] = None):
        self.path = path
        self.method = method.lower()
        self.operation_spec = operation_spec
        self.path_parameters = path_parameters or {}
        self.operation_id = operation_spec.get('operationId', f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}")
        self.summary = operation_spec.get('summary', '')
        self.description = operation_spec.get('description', '')
        self.tags = operation_spec.get('tags', [])
        self.parameters = operation_spec.get('parameters', [])
        self.request_body = operation_spec.get('requestBody', {})
        self.responses = operation_spec.get('responses', {})
        self.security = operation_spec.get('security', [])


class OpenAPILoader:
    """Loads and parses OpenAPI 3.0 specifications"""

    def __init__(self, spec_path: str):
        self.spec_path = Path(spec_path)
        self.spec = self._load_spec()

    def _load_spec(self) -> Dict[str, Any]:
        """Load OpenAPI specification from file"""
        if not self.spec_path.exists():
            raise FileNotFoundError(f"OpenAPI spec not found: {self.spec_path}")

        with open(self.spec_path, 'r') as f:
            if self.spec_path.suffix.lower() in ['.yaml', '.yml']:
                return yaml.safe_load(f)
            elif self.spec_path.suffix.lower() == '.json':
                return json.load(f)
            else:
                raise ValueError(f"Unsupported spec format: {self.spec_path.suffix}")

    def get_all_endpoints(self) -> List[APITestSpec]:
        """Extract all API endpoints from OpenAPI spec"""
        endpoints = []
        paths = self.spec.get('paths', {})

        for path, path_item in paths.items():
            # Extract path parameters
            path_params = {}
            for param in path_item.get('parameters', []):
                if param.get('in') == 'path':
                    path_params[param['name']] = param

            # Extract operations for each HTTP method
            for method in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                if method in path_item:
                    operation_spec = path_item[method]
                    endpoints.append(APITestSpec(
                        path=path,
                        method=method,
                        operation_spec=operation_spec,
                        path_parameters=path_params
                    ))

        return endpoints

    def get_endpoint_by_operation_id(self, operation_id: str) -> Optional[APITestSpec]:
        """Get specific endpoint by operation ID"""
        for endpoint in self.get_all_endpoints():
            if endpoint.operation_id == operation_id:
                return endpoint
        return None

    def get_endpoints_by_tag(self, tag: str) -> List[APITestSpec]:
        """Get all endpoints with a specific tag"""
        return [ep for ep in self.get_all_endpoints() if tag in ep.tags]


class APITestDataGenerator:
    """Generates test data based on OpenAPI schemas"""

    @staticmethod
    def generate_value_from_schema(schema: Dict[str, Any]) -> Any:
        """Generate a test value from a JSON schema"""
        if 'example' in schema:
            return schema['example']

        schema_type = schema.get('type', 'string')
        schema_format = schema.get('format')

        if schema_type == 'string':
            if schema_format == 'email':
                return 'test@example.com'
            elif schema_format == 'date-time':
                return '2024-01-01T00:00:00Z'
            elif schema_format == 'uuid':
                return '123e4567-e89b-12d3-a456-426614174000'
            elif schema_format == 'uri':
                return 'https://example.com'
            else:
                min_length = schema.get('minLength', 1)
                return 't' * max(min_length, 5)

        elif schema_type == 'integer':
            minimum = schema.get('minimum', 1)
            maximum = schema.get('maximum', 100)
            return minimum

        elif schema_type == 'number':
            minimum = schema.get('minimum', 1.0)
            return float(minimum)

        elif schema_type == 'boolean':
            return True

        elif schema_type == 'array':
            items_schema = schema.get('items', {})
            item_value = APITestDataGenerator.generate_value_from_schema(items_schema)
            return [item_value]

        elif schema_type == 'object':
            properties = schema.get('properties', {})
            required = schema.get('required', [])

            obj = {}
            for prop_name, prop_schema in properties.items():
                if prop_name in required or not prop_schema.get('nullable', False):
                    obj[prop_name] = APITestDataGenerator.generate_value_from_schema(prop_schema)
            return obj

        return None

    @staticmethod
    def generate_request_body(request_body_spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate request body data from OpenAPI spec"""
        if not request_body_spec:
            return None

        content = request_body_spec.get('content', {})
        if 'application/json' in content:
            schema = content['application/json'].get('schema', {})
            return APITestDataGenerator.generate_value_from_schema(schema)

        return None

    @staticmethod
    def generate_path_parameters(path: str, path_parameters: Dict[str, Any]) -> Dict[str, str]:
        """Generate path parameters for a given path"""
        params = {}

        # Extract parameter names from path
        import re
        param_names = re.findall(r'\{(\w+)\}', path)

        for param_name in param_names:
            if param_name in path_parameters:
                param_spec = path_parameters[param_name]
                params[param_name] = str(APITestDataGenerator.generate_value_from_schema(param_spec.get('schema', {'type': 'string'})))
            else:
                # Default parameter values
                if 'id' in param_name.lower():
                    params[param_name] = '123e4567-e89b-12d3-a456-426614174000'
                else:
                    params[param_name] = 'test_value'

        return params


class APIResponseValidator:
    """Validates API responses against OpenAPI specifications"""

    def __init__(self, openapi_loader: OpenAPILoader):
        self.openapi_loader = openapi_loader
        self.components = openapi_loader.spec.get('components', {})

    def validate_response(self, endpoint: APITestSpec, status_code: int,
                         response_data: Any, response_headers: Dict[str, str]) -> List[str]:
        """Validate response against OpenAPI specification"""
        errors = []

        # Check if status code is expected
        expected_status_codes = list(endpoint.responses.keys())

        # Handle default response
        if 'default' in endpoint.responses and str(status_code) not in expected_status_codes:
            expected_status_codes.append(str(status_code))

        if str(status_code) not in expected_status_codes and 'default' not in endpoint.responses:
            errors.append(f"Unexpected status code: {status_code}. Expected: {expected_status_codes}")

        # Get response specification
        response_spec = endpoint.responses.get(str(status_code)) or endpoint.responses.get('default', {})

        # Validate response body if present
        if response_data:
            content = response_spec.get('content', {})
            if 'application/json' in content:
                schema = content['application/json'].get('schema', {})
                validation_errors = self._validate_schema(response_data, schema, f"response[{status_code}]")
                errors.extend(validation_errors)

        # Validate headers
        expected_headers = response_spec.get('headers', {})
        for header_name, header_spec in expected_headers.items():
            if header_name.lower() in response_headers:
                header_value = response_headers[header_name.lower()]
                schema = header_spec.get('schema', {'type': 'string'})
                validation_errors = self._validate_schema(header_value, schema, f"header[{header_name}]")
                errors.extend(validation_errors)

        return errors

    def _validate_schema(self, data: Any, schema: Dict[str, Any], path: str = "") -> List[str]:
        """Validate data against JSON schema"""
        errors = []

        schema_type = schema.get('type')

        # Handle $ref
        if '$ref' in schema:
            ref_path = schema['$ref'].replace('#/components/schemas/', '')
            ref_schema = self.components.get('schemas', {}).get(ref_path, {})
            return self._validate_schema(data, ref_schema, path)

        # Handle allOf
        if 'allOf' in schema:
            for sub_schema in schema['allOf']:
                sub_errors = self._validate_schema(data, sub_schema, path)
                errors.extend(sub_errors)
            return errors

        # Handle anyOf
        if 'anyOf' in schema:
            any_errors = []
            for sub_schema in schema['anyOf']:
                sub_errors = self._validate_schema(data, sub_schema, path)
                if not sub_errors:
                    return []  # Valid against at least one schema
                any_errors.append(sub_errors)

            # If we're here, data didn't match any schema
            errors.append(f"{path}: Data doesn't match any of the anyOf schemas")
            return errors

        # Basic type validation
        if schema_type == 'string':
            if not isinstance(data, str):
                errors.append(f"{path}: Expected string, got {type(data).__name__}")
            else:
                # Check string constraints
                min_length = schema.get('minLength')
                max_length = schema.get('maxLength')
                if min_length and len(data) < min_length:
                    errors.append(f"{path}: String too short (min: {min_length})")
                if max_length and len(data) > max_length:
                    errors.append(f"{path}: String too long (max: {max_length})")

        elif schema_type == 'integer':
            if not isinstance(data, int) or isinstance(data, bool):
                errors.append(f"{path}: Expected integer, got {type(data).__name__}")
            else:
                # Check numeric constraints
                minimum = schema.get('minimum')
                maximum = schema.get('maximum')
                if minimum is not None and data < minimum:
                    errors.append(f"{path}: Integer too small (min: {minimum})")
                if maximum is not None and data > maximum:
                    errors.append(f"{path}: Integer too large (max: {maximum})")

        elif schema_type == 'number':
            if not isinstance(data, (int, float)) or isinstance(data, bool):
                errors.append(f"{path}: Expected number, got {type(data).__name__}")

        elif schema_type == 'boolean':
            if not isinstance(data, bool):
                errors.append(f"{path}: Expected boolean, got {type(data).__name__}")

        elif schema_type == 'array':
            if not isinstance(data, list):
                errors.append(f"{path}: Expected array, got {type(data).__name__}")
            else:
                # Check array constraints
                min_items = schema.get('minItems')
                max_items = schema.get('maxItems')
                if min_items and len(data) < min_items:
                    errors.append(f"{path}: Array too small (min: {min_items})")
                if max_items and len(data) > max_items:
                    errors.append(f"{path}: Array too large (max: {max_items})")

                # Validate items
                items_schema = schema.get('items', {})
                for i, item in enumerate(data):
                    item_errors = self._validate_schema(item, items_schema, f"{path}[{i}]")
                    errors.extend(item_errors)

        elif schema_type == 'object':
            if not isinstance(data, dict):
                errors.append(f"{path}: Expected object, got {type(data).__name__}")
            else:
                # Check required properties
                required = schema.get('required', [])
                for prop in required:
                    if prop not in data:
                        errors.append(f"{path}: Missing required property '{prop}'")

                # Validate properties
                properties = schema.get('properties', {})
                for prop_name, prop_value in data.items():
                    if prop_name in properties:
                        prop_errors = self._validate_schema(
                            prop_value, properties[prop_name], f"{path}.{prop_name}"
                        )
                        errors.extend(prop_errors)

        return errors


class APIContractTestRunner:
    """Main API contract test runner"""

    def __init__(self, spec_path: str, base_url: str = "http://test"):
        self.openapi_loader = OpenAPILoader(spec_path)
        self.validator = APIResponseValidator(self.openapi_loader)
        self.base_url = base_url
        self.test_client = TestClient(app)

    def run_endpoint_test(self, endpoint: APITestSpec, auth_headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Run contract test for a single endpoint"""
        result = {
            'endpoint': endpoint.operation_id,
            'method': endpoint.method.upper(),
            'path': endpoint.path,
            'success': False,
            'status_code': None,
            'response_data': None,
            'errors': [],
            'warnings': []
        }

        try:
            # Generate request data
            request_data = APITestDataGenerator.generate_request_body(endpoint.request_body)
            path_params = APITestDataGenerator.generate_path_parameters(endpoint.path, endpoint.path_parameters)

            # Build URL
            url = endpoint.path
            for param_name, param_value in path_params.items():
                url = url.replace(f'{{{param_name}}}', str(param_value))

            # Make request
            headers = auth_headers or {}
            if endpoint.method == 'get':
                response = self.test_client.get(url, headers=headers, params=request_data)
            elif endpoint.method == 'post':
                response = self.test_client.post(url, headers=headers, json=request_data)
            elif endpoint.method == 'put':
                response = self.test_client.put(url, headers=headers, json=request_data)
            elif endpoint.method == 'delete':
                response = self.test_client.delete(url, headers=headers)
            elif endpoint.method == 'patch':
                response = self.test_client.patch(url, headers=headers, json=request_data)
            else:
                result['errors'].append(f"Unsupported HTTP method: {endpoint.method}")
                return result

            # Record response
            result['status_code'] = response.status_code
            try:
                result['response_data'] = response.json()
            except:
                result['response_data'] = response.text

            # Validate response
            response_headers = dict(response.headers)
            validation_errors = self.validator.validate_response(
                endpoint, response.status_code, result['response_data'], response_headers
            )

            if validation_errors:
                result['errors'].extend(validation_errors)
            else:
                result['success'] = True

        except Exception as e:
            result['errors'].append(f"Test execution error: {str(e)}")

        return result

    def run_all_tests(self, auth_headers: Dict[str, str] = None,
                     tags: List[str] = None) -> Dict[str, Any]:
        """Run contract tests for all endpoints or specific tags"""
        if tags:
            endpoints = []
            for tag in tags:
                endpoints.extend(self.openapi_loader.get_endpoints_by_tag(tag))
        else:
            endpoints = self.openapi_loader.get_all_endpoints()

        results = {
            'total_endpoints': len(endpoints),
            'passed': 0,
            'failed': 0,
            'results': []
        }

        for endpoint in endpoints:
            result = self.run_endpoint_test(endpoint, auth_headers)
            results['results'].append(result)

            if result['success']:
                results['passed'] += 1
            else:
                results['failed'] += 1

        return results


# Test Fixtures
@pytest.fixture
def api_contract_runner():
    """Create API contract test runner"""
    spec_path = "docs/ab_testing_openapi.yaml"
    return APIContractTestRunner(spec_path)


@pytest.fixture
def admin_auth_headers(test_admin_user):
    """Create admin authentication headers for API testing"""
    from src.core.security import create_access_token
    token = create_access_token(data={"sub": str(test_admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_auth_headers(test_regular_user):
    """Create user authentication headers for API testing"""
    from src.core.security import create_access_token
    token = create_access_token(data={"sub": str(test_regular_user.id)})
    return {"Authorization": f"Bearer {token}"}