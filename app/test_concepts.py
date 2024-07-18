import requests
import json

BASE_URL = "http://localhost:5000"

def print_response(response):
    print(f"Status Code: {response.status_code}")
    print("Response:")
    print(json.dumps(response.json(), indent=2))
    print("\n" + "="*50 + "\n")

def create_concept(name, description, related_concepts):
    print(f"Creating Concept: {name}")
    url = f"{BASE_URL}/concept"
    data = {
        "name": name,
        "description": description,
        "related_concepts": related_concepts
    }
    response = requests.post(url, json=data)
    print_response(response)

def get_concept(name):
    print(f"Getting Concept: {name}")
    url = f"{BASE_URL}/concept/{name}"
    response = requests.get(url)
    print_response(response)

def explore_concept(name):
    print(f"Exploring Concept: {name}")
    url = f"{BASE_URL}/explore_concept"
    data = {"concept": name}
    response = requests.post(url, json=data)
    print_response(response)

def run_c_trainer_tests():
    # Create main C programming concept
    create_concept(
        "C Programming",
        "A general-purpose, procedural computer programming language supporting structured programming, lexical variable scope, and recursion, with a static type system",
        [
            {"name": "Variables", "description": "Named storage locations in memory that hold data", "relationship": "FUNDAMENTAL_CONCEPT"},
            {"name": "Functions", "description": "Reusable blocks of code that perform specific tasks", "relationship": "FUNDAMENTAL_CONCEPT"},
            {"name": "Control Structures", "description": "Statements that control the flow of execution in a program", "relationship": "FUNDAMENTAL_CONCEPT"}
        ]
    )

    # Create and explore related concepts
    create_concept(
        "Variables",
        "Named storage locations in memory that hold data in C programming",
        [
            {"name": "Data Types", "description": "Specifies the type of data that a variable can store", "relationship": "RELATED_TO"},
            {"name": "Scope", "description": "Defines where in the program a variable can be accessed", "relationship": "RELATED_TO"}
        ]
    )

    create_concept(
        "Functions",
        "Reusable blocks of code that perform specific tasks in C programming",
        [
            {"name": "Parameters", "description": "Variables used to pass data into functions", "relationship": "COMPONENT"},
            {"name": "Return Types", "description": "Specifies the type of data a function returns", "relationship": "COMPONENT"}
        ]
    )

    create_concept(
        "Control Structures",
        "Statements that control the flow of execution in a C program",
        [
            {"name": "If-Else Statements", "description": "Conditional execution based on a boolean expression", "relationship": "TYPE_OF"},
            {"name": "Loops", "description": "Repeated execution of a block of code", "relationship": "TYPE_OF"}
        ]
    )

    # Get and explore concepts
    get_concept("C Programming")
    get_concept("Variables")
    get_concept("Functions")
    get_concept("Control Structures")

    explore_concept("Pointers")
    get_concept("Pointers")

if __name__ == "__main__":
    run_c_trainer_tests()