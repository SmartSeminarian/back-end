import requests
import json

BASE_URL = "http://localhost:5000"

def print_response(response):
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    print("\n" + "="*50 + "\n")

def test_create_concept():
    print("Testing: Create Concept")
    url = f"{BASE_URL}/concept"
    data = {
        "name": "Machine Learning",
        "description": "A field of AI that uses statistical techniques to give computer systems the ability to learn from data",
        "related_concepts": [
            {"name": "Deep Learning", "relationship": "IS_A"},
            {"name": "Data Science", "relationship": "RELATED_TO"}
        ]
    }
    response = requests.post(url, json=data)
    print_response(response)

def test_get_concept(name):
    print(f"Testing: Get Concept '{name}'")
    url = f"{BASE_URL}/concept/{name}"
    response = requests.get(url)
    print_response(response)

def test_explore_concept(name):
    print(f"Testing: Explore Concept '{name}'")
    url = f"{BASE_URL}/explore_concept"
    data = {"concept": name}
    response = requests.post(url, json=data)
    print_response(response)

def run_tests():
    test_create_concept()
    test_get_concept("Machine Learning")
    test_get_concept("Deep Learning")
    test_get_concept("Data Science")
    test_explore_concept("Neural Networks")
    test_get_concept("Neural Networks")

if __name__ == "__main__":
    run_tests()