import sys
import os
import requests
import time
from datetime import datetime, timedelta

# Base URL for the running server
BASE_URL = "http://127.0.0.1:8005"

def get_access_token():
    """Authenticate and return access token."""
    try:
        # Try default credentials
        response = requests.post(
            f"{BASE_URL}/api/v1/token",
            data={"username": "admin", "password": "!234qwer"},
            timeout=5
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"Login failed: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"Login request failed: {e}")
        return None

def test_trend_analysis_endpoints():
    # Define a date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    params = {"start_date": start_date, "end_date": end_date}
    
    print(f"Testing Trend Analysis API at {BASE_URL}")
    print(f"Date Range: {start_date} to {end_date}")
    print("-" * 50)

    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/docs", timeout=2)
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to server at {BASE_URL}")
        print("Please ensure the backend server is running:")
        print("uvicorn webapp.main:app --reload --host 0.0.0.0 --port 8005")
        return

    # Authenticate
    token = get_access_token()
    if not token:
        print("Skipping tests due to authentication failure.")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    print("Authentication successful.")

    # 1. Price Trend
    print("\n1. Testing /price-trend...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/trend-analysis/price-trend", params=params, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Daily Trends Count: {len(data.get('daily_trends', []))}")
            print(f"Period Trends Keys: {list(data.get('period_trends', {}).keys())}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 2. Weekday Pattern
    print("\n2. Testing /weekday-pattern...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/trend-analysis/weekday-pattern", params=params, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Distribution Count: {len(data.get('distribution', []))}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 3. Volatility
    print("\n3. Testing /volatility...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/trend-analysis/volatility", params=params, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Daily Volatility Count: {len(data.get('daily_volatility', []))}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 4. Arbitrage
    print("\n4. Testing /arbitrage...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/trend-analysis/arbitrage", params=params, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Daily Arbitrage Count: {len(data.get('daily_arbitrage', []))}")
            print(f"Summary: {data.get('summary')}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    # 5. Anomaly
    print("\n5. Testing /anomaly...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/trend-analysis/anomaly", params=params, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Events: {list(data.get('events', {}).keys())}")
            print(f"Daily Extremums Count: {len(data.get('daily_extremums', []))}")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_trend_analysis_endpoints()
