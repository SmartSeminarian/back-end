Added separate docker container for neo4j graph database. To test locally docker compose:
```
./init-local-env.sh
docker compose up --build
docker exec -it back-end /bin/bash (To get access to backend container's terminal)
python3 test_concepts.py (In container's terminal)
Now browse to localhost:7474
Login with username=neo4j , password=secret
```
Tben test it with

```python3 login_test.py```
## Database Structure

### Table 1: Tokens
| Column Name | Description |
|-------------|-------------|
| token_name  | Identifier for the token |
| token       | Actual token value |


1. The user sends a request in the format: 
    
```python
login_data = {
    "github_username": "test_username",
    "token": "test:VongOahophufshepwucsimyig5ogukir"
}
response = requests.post(f"{BASE_URL}/login", json=login_data)
```    
Then he get a response with session_id.

For now it's only one valid token, so you can test it.

### Table 2: GitHub Users
| Column Name    | Description |
|----------------|-------------|
| github_username| GitHub username |

### Table 3: Sessions
| Column Name     | Description     |
|-----------------|-----------------|
| session_id      | Session_id      |
| github_username | github_username |

### Table 4: User Problems
| Column Name    | Description |
|----------------|-------------|
 |sequential numbers|
 | problem_id     | Unique problem identifier |
 | github_username| GitHub username |

### Table 5: Problems
| Column Name | Description |
|-------------|-------------|
| problem_id  | Unique problem identifier |
| description | Problem description |
| input       | Input specification |
| output      | Output specification |

