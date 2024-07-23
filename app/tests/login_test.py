import requests
import json

BASE_URL = "http://localhost:5000"

def test_login_and_protected_endpoint():
    login_data = {
        "github_username": "test_username",
        "token": "test:VongOahophufshepwucsimyig5ogukir"
    }
    response = requests.post(f"{BASE_URL}/login", json=login_data)
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    headers = {"X-Session-ID": session_id}
    response = requests.get(f"{BASE_URL}/problem", headers=headers)
    assert response.status_code == 200

    response = requests.get(f"{BASE_URL}/problem")
    assert response.status_code == 401

    headers = {"X-Session-ID": "invalid_session_id"}
    response = requests.get(f"{BASE_URL}/problem", headers=headers)
    assert response.status_code == 401

    print("All tests have been passed!")

if __name__ == "__main__":
    test_login_and_protected_endpoint()