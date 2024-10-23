import pytest
import requests
import json
import uuid

BASE_URL = "http://service:5050"
SESSION_ID = "54b180f6b7e8591d912eca45bcde217f"


@pytest.fixture(scope="module")
def session_id():
    url = f"{BASE_URL}/login"
    data = {
        "github_username": "test_user",
        "token": "test:VongOahophufshepwucsimyig5ogukir"
    }
    response = requests.post(url, json=data)
    assert response.status_code == 200
    session_data = response.json()
    assert "session_id" in session_data
    return session_data["session_id"]

@pytest.fixture(scope="module")
def headers(session_id):
    return {
        "Content-Type": "application/json",
        "X-Session-ID": session_id
    }

def test_login(session_id):
    assert session_id is not None


def create_unique_concept(headers):
    url = f"{BASE_URL}/concept"
    unique_name = f"Test Concept {uuid.uuid4()}"
    data = {
        "name": unique_name,
        "description": f"This is a test concept: {unique_name}",
        "difficulty": 2
    }
    response = requests.post(url, headers=headers, json=data)
    assert response.status_code == 201
    assert "id" in response.json()
    return response.json()["id"], unique_name


def test_create_concept(headers):
    concept_id, _ = create_unique_concept(headers)
    assert concept_id is not None


def test_get_concept(headers):
    concept_id, concept_name = create_unique_concept(headers)
    url = f"{BASE_URL}/concept/{concept_id}"
    response = requests.get(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == concept_name


def test_update_concept(headers):
    concept_id, _ = create_unique_concept(headers)
    url = f"{BASE_URL}/concept/{concept_id}"
    updated_name = f"Updated Test Concept {uuid.uuid4()}"
    data = {
        "name": updated_name,
        "description": f"This is an updated test concept: {updated_name}",
        "difficulty": 3
    }
    response = requests.put(url, headers=headers, json=data)
    assert response.status_code == 200
    assert response.json()["name"] == updated_name
    assert "version" in response.json()


def test_delete_concept(headers):
    concept_id, _ = create_unique_concept(headers)
    url = f"{BASE_URL}/concept/{concept_id}"
    response = requests.delete(url, headers=headers)
    assert response.status_code == 200


def test_get_all_concepts(headers):
    create_unique_concept(headers)
    url = f"{BASE_URL}/concept"
    response = requests.get(url, headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0


def test_bind_concepts(headers):
    concept_id1, _ = create_unique_concept(headers)
    concept_id2, _ = create_unique_concept(headers)
    url = f"{BASE_URL}/concept/bind"
    data = {
        "source_id": concept_id1,
        "target_id": concept_id2,
        "relation": "is_related_to"
    }
    response = requests.post(url, headers=headers, json=data)
    assert response.status_code == 201
    assert response.json()["source_id"] == concept_id1
    assert response.json()["target_id"] == concept_id2


def test_unbind_concepts(headers):
    concept_id1, name1 = create_unique_concept(headers)
    concept_id2, name2 = create_unique_concept(headers)

    print(f"Created concepts: {concept_id1} ({name1}) and {concept_id2} ({name2})")

    # First, bind the concepts
    bind_url = f"{BASE_URL}/concept/bind"
    bind_data = {
        "source_id": concept_id1,
        "target_id": concept_id2,
        "relation": "is_related_to"
    }
    bind_response = requests.post(bind_url, headers=headers, json=bind_data)
    assert bind_response.status_code == 201
    print(f"Bind response: {bind_response.json()}")

    # Now, unbind them
    unbind_url = f"{BASE_URL}/concept/unbind"
    unbind_data = {
        "source_id": concept_id1,
        "target_id": concept_id2
    }
    response = requests.post(unbind_url, headers=headers, json=unbind_data)
    print(f"Unbind status code: {response.status_code}")
    print(f"Unbind response: {response.text}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0


def test_version():
    url = f"{BASE_URL}/version"
    response = requests.get(url)
    assert response.status_code == 200
    assert "version" in response.json()