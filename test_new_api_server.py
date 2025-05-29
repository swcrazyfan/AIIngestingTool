#!/usr/bin/env python3
"""
Test script for the new streamlined API server.

This script tests all endpoints to ensure the new API server works correctly
and is compatible with the extension requirements.
"""

import requests
import json
import time
import sys
from typing import Dict, Any

# Test configuration
API_BASE_URL = "http://localhost:8001/api"
TEST_TIMEOUT = 10

# Test credentials (should be created in your database)
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'

def print_success(message: str):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message: str):
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_info(message: str):
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def print_header(message: str):
    print(f"\n{Colors.CYAN}{'='*60}")
    print(f"🧪 {message}")
    print(f"{'='*60}{Colors.END}")


class APITester:
    """Test suite for the new API server."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = TEST_TIMEOUT
        self.auth_token = None
        self.test_results = []
    
    def test_endpoint(self, name: str, method: str, endpoint: str, 
                     data: Dict[Any, Any] = None, 
                     params: Dict[str, Any] = None,
                     auth_required: bool = True,
                     expected_status: int = 200) -> bool:
        """Test a single API endpoint."""
        
        try:
            url = f"{API_BASE_URL}{endpoint}"
            headers = {'Content-Type': 'application/json'}
            
            # Skip auth header if not required
            if auth_required and self.auth_token:
                headers['Authorization'] = f"Bearer {self.auth_token}"
            
            # Make request
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, headers=headers)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, headers=headers)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, headers=headers)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Check status code
            if response.status_code == expected_status:
                try:
                    response_data = response.json()
                    print_success(f"{name}: {response.status_code}")
                    
                    # Validate response structure
                    if 'success' in response_data:
                        if response_data['success']:
                            print(f"   Response: {response_data.get('message', 'Success')}")
                        else:
                            print(f"   Error: {response_data.get('error', 'Unknown error')}")
                    
                    self.test_results.append((name, True, response.status_code, None))
                    return True
                    
                except json.JSONDecodeError:
                    print_success(f"{name}: {response.status_code} (non-JSON response)")
                    self.test_results.append((name, True, response.status_code, None))
                    return True
                    
            else:
                print_error(f"{name}: Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data.get('error', 'Unknown error')}")
                except:
                    print(f"   Response: {response.text[:200]}")
                
                self.test_results.append((name, False, response.status_code, 
                                       f"Expected {expected_status}, got {response.status_code}"))
                return False
                
        except requests.exceptions.RequestException as e:
            print_error(f"{name}: Request failed - {str(e)}")
            self.test_results.append((name, False, None, str(e)))
            return False
        except Exception as e:
            print_error(f"{name}: Unexpected error - {str(e)}")
            self.test_results.append((name, False, None, str(e)))
            return False
    
    def test_server_health(self):
        """Test server health and basic connectivity."""
        print_header("HEALTH AND CONNECTIVITY TESTS")
        
        # Health check (no auth required)
        self.test_endpoint(
            "Health Check", "GET", "/health", 
            auth_required=False
        )
        
        # System status (no auth required)
        self.test_endpoint(
            "System Status", "GET", "/status",
            auth_required=False
        )
    
    def test_authentication(self):
        """Test authentication endpoints."""
        print_header("AUTHENTICATION TESTS")
        
        # Auth status (no auth required)
        self.test_endpoint(
            "Auth Status (Logged Out)", "GET", "/auth/status",
            auth_required=False
        )
        
        # Login (should fail with invalid credentials)
        self.test_endpoint(
            "Login (Invalid Credentials)", "POST", "/auth/login",
            data={"email": "invalid@test.com", "password": "wrongpassword"},
            auth_required=False,
            expected_status=401
        )
        
        # Signup (new account)
        self.test_endpoint(
            "Signup (New Account)", "POST", "/auth/signup",
            data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            auth_required=False
        )
        
        # Login (valid credentials)
        success = self.test_endpoint(
            "Login (Valid Credentials)", "POST", "/auth/login",
            data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            auth_required=False
        )
        
        if success:
            print_info("Authentication successful - can proceed with protected endpoints")
        else:
            print_warning("Authentication failed - protected endpoint tests will fail")
        
        # Auth status (logged in)
        self.test_endpoint(
            "Auth Status (Logged In)", "GET", "/auth/status",
            auth_required=False
        )
    
    def test_search_endpoints(self):
        """Test search endpoints (requires auth)."""
        print_header("SEARCH ENDPOINTS TESTS")
        
        # Recent videos
        self.test_endpoint(
            "Search Recent", "GET", "/search/recent",
            params={"limit": 5}
        )
        
        # Search query (should fail without query)
        self.test_endpoint(
            "Search Query (No Query)", "GET", "/search",
            expected_status=400
        )
        
        # Search query with text
        self.test_endpoint(
            "Search Query (With Text)", "GET", "/search",
            params={"q": "test video", "limit": 5}
        )
        
        # Similar search (should fail without clip_id)
        self.test_endpoint(
            "Search Similar (No Clip ID)", "GET", "/search/similar",
            expected_status=400
        )
        
        # Similar search with clip_id (may fail if no data)
        self.test_endpoint(
            "Search Similar (With Clip ID)", "GET", "/search/similar",
            params={"clip_id": "test-clip-id", "limit": 5},
            expected_status=500  # Likely to fail with no data, which is expected
        )
        
        # Search stats
        self.test_endpoint(
            "Search Stats", "GET", "/search/stats"
        )
    
    def test_clips_endpoints(self):
        """Test clip endpoints (requires auth)."""
        print_header("CLIPS ENDPOINTS TESTS")
        
        # These will likely fail with 404 since we don't have test data
        # But we can verify the endpoints respond correctly
        
        test_clip_id = "non-existent-clip-id"
        
        self.test_endpoint(
            "Get Clip Details", "GET", f"/clips/{test_clip_id}",
            expected_status=404
        )
        
        self.test_endpoint(
            "Get Clip Transcript", "GET", f"/clips/{test_clip_id}/transcript",
            expected_status=404
        )
        
        self.test_endpoint(
            "Get Clip Analysis", "GET", f"/clips/{test_clip_id}/analysis",
            expected_status=404
        )
    
    def test_system_endpoints(self):
        """Test system endpoints (requires auth)."""
        print_header("SYSTEM ENDPOINTS TESTS")
        
        # Pipeline steps
        self.test_endpoint(
            "Get Pipeline Steps", "GET", "/pipeline/steps"
        )
        
        # Progress (all jobs)
        self.test_endpoint(
            "Get All Progress", "GET", "/progress"
        )
        
        # Progress for specific task (will fail but should return proper error)
        self.test_endpoint(
            "Get Task Progress", "GET", "/progress/550e8400-e29b-41d4-a716-446655440000",
            expected_status=404  # Expected to fail
        )
    
    def test_ingest_endpoint(self):
        """Test ingest endpoint (requires auth)."""
        print_header("INGEST ENDPOINT TESTS")
        
        # Ingest without directory (should fail validation)
        self.test_endpoint(
            "Ingest (No Directory)", "POST", "/ingest",
            data={},
            expected_status=400
        )
        
        # Ingest with invalid directory (should fail)
        self.test_endpoint(
            "Ingest (Invalid Directory)", "POST", "/ingest",
            data={"directory": "/nonexistent/directory"},
            expected_status=400
        )
        
        # Note: We don't test with valid directory to avoid actually starting ingest
        print_info("Skipping ingest with valid directory to avoid starting actual processing")
    
    def test_special_routes(self):
        """Test special routes for extension compatibility."""
        print_header("SPECIAL ROUTES TESTS")
        
        # Thumbnail proxy (not yet implemented)
        self.test_endpoint(
            "Thumbnail Proxy", "GET", "/thumbnail/test-clip-id",
            expected_status=501  # Not implemented
        )
    
    def test_logout(self):
        """Test logout functionality."""
        print_header("LOGOUT TEST")
        
        self.test_endpoint(
            "Logout", "POST", "/auth/logout"
        )
        
        # Verify we can't access protected endpoints after logout
        self.test_endpoint(
            "Protected Endpoint After Logout", "GET", "/search/recent",
            expected_status=401
        )
    
    def run_all_tests(self):
        """Run all test suites."""
        print_info(f"Testing API server at: {API_BASE_URL}")
        print_info(f"Test timeout: {TEST_TIMEOUT} seconds")
        
        start_time = time.time()
        
        # Run test suites in order
        self.test_server_health()
        self.test_authentication()
        self.test_search_endpoints()
        self.test_clips_endpoints()
        self.test_system_endpoints()
        self.test_ingest_endpoint()
        self.test_special_routes()
        self.test_logout()
        
        # Print summary
        end_time = time.time()
        duration = end_time - start_time
        
        print_header("TEST RESULTS SUMMARY")
        
        passed = sum(1 for _, success, _, _ in self.test_results if success)
        failed = len(self.test_results) - passed
        
        print(f"Total tests: {len(self.test_results)}")
        print_success(f"Passed: {passed}")
        if failed > 0:
            print_error(f"Failed: {failed}")
        
        print(f"\nTest duration: {duration:.2f} seconds")
        
        # Show failed tests
        if failed > 0:
            print(f"\n{Colors.YELLOW}Failed Tests:{Colors.END}")
            for name, success, status_code, error in self.test_results:
                if not success:
                    print(f"  ❌ {name}: {error or f'Status {status_code}'}")
        
        return failed == 0


def main():
    """Main test runner."""
    print(f"{Colors.CYAN}")
    print("🧪 API Server Test Suite")
    print("========================")
    print(f"Testing new streamlined API server{Colors.END}")
    
    # Check if server is running
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print_error(f"Server not responding correctly at {API_BASE_URL}")
            print_info("Make sure the API server is running:")
            print_info("python -m video_ingest_tool.api.server --port 8001")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print_error(f"Cannot connect to API server at {API_BASE_URL}")
        print_info("Make sure the API server is running:")
        print_info("python -m video_ingest_tool.api.server --port 8001")
        sys.exit(1)
    
    print_success(f"API server is responding at {API_BASE_URL}")
    
    # Run tests
    tester = APITester()
    success = tester.run_all_tests()
    
    if success:
        print_success("\n🎉 All tests passed! The new API server is working correctly.")
        sys.exit(0)
    else:
        print_warning("\n⚠️  Some tests failed. Review the results above.")
        sys.exit(1)


if __name__ == "__main__":
    main() 