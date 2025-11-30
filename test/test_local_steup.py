"""
Test script to verify local Splunk and Jira setup
"""

import requests
import json
import os
from dotenv import load_dotenv
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Load environment
load_dotenv()

def print_header(text):
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{text.center(60)}")
    print(f"{Fore.CYAN}{'='*60}\n")

def print_success(text):
    print(f"{Fore.GREEN}✓ {text}")

def print_error(text):
    print(f"{Fore.RED}✗ {text}")

def print_info(text):
    print(f"{Fore.YELLOW}ℹ {text}")

def test_splunk():
    """Test Splunk connection with token"""
    print_header("Testing Splunk Connection (Token Auth)")
    
    splunk_host = os.getenv("SPLUNK_HOST", "http://localhost:8087")
    splunk_hec = os.getenv("SPLUNK_HEC_URL", "https://localhost:8088")
    splunk_token = os.getenv("SPLUNK_TOKEN", "")
    
    print_info(f"Splunk UI: {splunk_host}")
    print_info(f"Splunk HEC: {splunk_hec}")
    
    if not splunk_token:
        print_error("SPLUNK_TOKEN not set in .env")
        print_info("Generate token in Splunk: Settings > Data Inputs > HTTP Event Collector")
        return False
    
    print_info(f"Token: {splunk_token[:10]}...{splunk_token[-5:]}")
    
    # Test 1: Check if Splunk UI is accessible
    try:
        response = requests.get(splunk_host, timeout=5, verify=False)
        if response.status_code == 200:
            print_success("Splunk UI is accessible")
        else:
            print_success(f"Splunk UI responded (status: {response.status_code})")
    except Exception as e:
        print_error(f"Cannot connect to Splunk UI: {e}")
        return False
    
    # Test 2: Test HEC endpoint with token
    try:
        test_event = {"event": "AITTA test event", "sourcetype": "aitta:test"}
        response = requests.post(
            f"{splunk_hec}/services/collector/event",
            headers={"Authorization": f"Splunk {splunk_token}"},
            json=test_event,
            verify=False,
            timeout=5
        )
        if response.status_code == 200:
            print_success("HEC token is valid and working")
        else:
            print_error(f"HEC returned status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print_error(f"HEC test failed: {e}")
        return False
    
    # Test 3: Test REST API with Bearer token
    try:
        response = requests.get(
            f"{splunk_host}/services/server/info",
            headers={"Authorization": f"Bearer {splunk_token}"},
            verify=False,
            timeout=5
        )
        if response.status_code == 200:
            print_success("Splunk REST API token authentication successful")
        elif response.status_code == 401:
            print_info("REST API with Bearer: Not authorized (this is normal for HEC-only tokens)")
        else:
            print_info(f"REST API returned: {response.status_code}")
    except Exception as e:
        print_info(f"REST API test: {e}")
    
    return True

def test_jira():
    """Test Jira connection with token"""
    print_header("Testing Jira Connection (Token Auth)")
    
    jira_url = os.getenv("JIRA_URL", "http://localhost:8090")
    jira_token = os.getenv("JIRA_TOKEN", "")
    jira_project = os.getenv("JIRA_PROJECT_KEY", "TEST")
    
    print_info(f"Jira URL: {jira_url}")
    print_info(f"Project: {jira_project}")
    
    if not jira_token:
        print_error("JIRA_TOKEN not set in .env")
        print_info("Generate token in Jira: Profile > Personal Access Tokens")
        return False
    
    print_info(f"Token: {jira_token[:10]}...{jira_token[-5:]}")
    
    # Test 1: Check if Jira is accessible
    try:
        response = requests.get(jira_url, timeout=5)
        if response.status_code == 200:
            print_success("Jira is accessible")
        else:
            print_success(f"Jira responded (status: {response.status_code})")
    except Exception as e:
        print_error(f"Cannot connect to Jira: {e}")
        return False
    
    # Test 2: Test token authentication
    try:
        response = requests.get(
            f"{jira_url}/rest/api/2/myself",
            headers={"Authorization": f"Bearer {jira_token}"},
            timeout=5
        )
        if response.status_code == 200:
            user_data = response.json()
            print_success(f"Token authentication successful!")
            print_success(f"Authenticated as: {user_data.get('displayName', 'Unknown')}")
        else:
            print_error(f"Token authentication failed: {response.status_code}")
            print_error(response.text)
            return False
    except Exception as e:
        print_error(f"Authentication test failed: {e}")
        return False
    
    # Test 3: Check if project exists
    try:
        response = requests.get(
            f"{jira_url}/rest/api/2/project/{jira_project}",
            headers={"Authorization": f"Bearer {jira_token}"},
            timeout=5
        )
        if response.status_code == 200:
            project_data = response.json()
            print_success(f"Project '{jira_project}' found: {project_data.get('name', '')}")
        else:
            print_error(f"Project '{jira_project}' not found (status: {response.status_code})")
            print_info("Available projects:")
            
            # List all projects
            projects_response = requests.get(
                f"{jira_url}/rest/api/2/project",
                headers={"Authorization": f"Bearer {jira_token}"},
                timeout=5
            )
            if projects_response.status_code == 200:
                projects = projects_response.json()
                for p in projects:
                    print_info(f"  - {p['key']}: {p['name']}")
            
            return False
    except Exception as e:
        print_error(f"Project check failed: {e}")
        return False
    
    # Test 4: Test creating a ticket (optional - uncomment to test)
    print_info("Skipping ticket creation test (to avoid cluttering Jira)")
    print_info("To test ticket creation, uncomment the test in the script")
    
    return True

def test_gemini():
    """Test Gemini API"""
    print_header("Testing Gemini API")
    
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    
    if not gemini_key:
        print_error("GEMINI_API_KEY not set in .env")
        return False
    
    if gemini_key == "your-gemini-api-key-here":
        print_error("GEMINI_API_KEY is still set to placeholder value")
        print_info("Get your key from: https://makersuite.google.com/app/apikey")
        return False
    
    print_info(f"API Key: {gemini_key[:10]}...{gemini_key[-5:]}")
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        
        response = model.generate_content("Say 'AITTA test successful' if you can read this.")
        
        if response.text:
            print_success("Gemini API is working")
            print_info(f"Response: {response.text[:100]}")
        else:
            print_error("Gemini API returned empty response")
            return False
            
    except Exception as e:
        print_error(f"Gemini API test failed: {e}")
        return False
    
    return True

def test_backend():
    """Test if AITTA backend is running"""
    print_header("Testing AITTA Backend")
    
    backend_url = "http://localhost:8000"
    
    try:
        response = requests.get(backend_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success("Backend is running")
            print_info(f"Version: {data.get('version', 'unknown')}")
            print_info(f"Status: {data.get('status', 'unknown')}")
            print_info(f"Mock mode: {data.get('mock_mode', 'unknown')}")
            print_info(f"LLM: {data.get('llm_provider', 'unknown')}")
        else:
            print_error(f"Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Cannot connect to backend: {e}")
        print_info("Make sure backend is running: python main.py")
        return False
    
    return True

def main():
    """Run all tests"""
    print(f"{Fore.MAGENTA}{Style.BRIGHT}")
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║         AITTA Local Setup Verification Test              ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    print(Style.RESET_ALL)
    
    # Suppress SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    results = {}
    
    # Run tests
    results['splunk'] = test_splunk()
    results['jira'] = test_jira()
    results['gemini'] = test_gemini()
    results['backend'] = test_backend()
    
    # Summary
    print_header("Test Summary")
    
    for test_name, passed in results.items():
        if passed:
            print_success(f"{test_name.capitalize()}: PASSED")
        else:
            print_error(f"{test_name.capitalize()}: FAILED")
    
    # Overall result
    all_passed = all(results.values())
    
    print("\n")
    if all_passed:
        print(f"{Fore.GREEN}{Style.BRIGHT}🎉 All tests passed! Your AITTA setup is ready!{Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}Next steps:")
        print(f"{Fore.WHITE}1. Start backend: python main.py")
        print(f"{Fore.WHITE}2. Start frontend: python -m http.server 8080")
        print(f"{Fore.WHITE}3. Open dashboard: http://localhost:8080")
        print(f"{Fore.WHITE}4. Run demo: python demo.py")
    else:
        print(f"{Fore.RED}{Style.BRIGHT}⚠️  Some tests failed. Please fix the issues above.{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}Common fixes:")
        print(f"{Fore.WHITE}1. Check .env file has correct credentials")
        print(f"{Fore.WHITE}2. Ensure Splunk is running on localhost:8087")
        print(f"{Fore.WHITE}3. Ensure Jira is running on localhost:8090")
        print(f"{Fore.WHITE}4. Get Gemini API key from https://makersuite.google.com/app/apikey")

if __name__ == "__main__":
    main()