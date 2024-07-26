#!/bin/bash

check_status_code() 
{
    if [ "$1" -ne $2 ]; then
        echo "Error: Status code for $3 request must be $2"
        rm -f ./response.json
        exit 1
    fi
}

URL="localhost:5000"

# Get Session-ID
login_response=$(curl -s -X POST $URL/login \
    -H "Content-Type: application/json" \
    -d '{"github_username": "user", "token": "test:VongOahophufshepwucsimyig5ogukir"}')

session_id=$(echo $login_response | jq --raw-output '.session_id') 
echo "Session ID: $session_id"

# Version Request
status_code=$(curl -s -o response.json \
    -w "%{http_code}" \
    -X GET $URL/version \
    -H "accept: application/json")
echo "Version: HTTP Status Code = $status_code"

check_status_code $status_code 200 "version"

# Post concept
status_code=$(curl -s -o response.json \
    -w "%{http_code}" \
    -X POST $URL/concept \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d '{
    "name": "C-Programming",
    "description": "A general-purpose, procedural computer programming language supporting structured programming, lexical variable scope, and recursion, with a static type system",
    "related_concepts": [
        {"name": "Variables", "description": "Named storage locations in memory that hold data", "relationship": "FUNDAMENTAL_CONCEPT"},
        {"name": "Functions", "description": "Reusable blocks of code that perform specific tasks", "relationship": "FUNDAMENTAL_CONCEPT"},
        {"name": "Control Structures", "description": "Statements that control the flow of execution in a program", "relationship": "FUNDAMENTAL_CONCEPT"}
    ]
}')
echo "Post Concept: HTTP Status Code = $status_code"
check_status_code $status_code 201 "post concept"

# Get concept by name
status_code=$(curl -s -o response.json \
    -w "%{http_code}" \
    -X GET $URL/concept/C-Programming \
    -H 'accept: application/json')
echo "Get Concept(that exists): HTTP Status Code = $status_code"
check_status_code $status_code 200 "get concept"

# Get invalid concept 
status_code=$(curl -s -o response.json \
    -w "%{http_code}" \
    -X GET $URL/concept/SmartSeminarian \
    -H 'accept: application/json')
echo "Get Concept(that does not exist): HTTP Status Code = $status_code"
check_status_code $status_code 404 "get invalid concept"

# Problem request
status_code=$(curl -s -o response.json \
    -w "%{http_code}" \
    -X GET $URL/problem \
    -H "accept: application/json" \
    -H "X-Session-ID: $session_id" )
problemId=$(cat response.json | jq -r .id) # Extract problemId from json to use in Submit Solution
echo "Problem: HTTP Status Code = $status_code"
check_status_code $status_code 200 "get problem"

# Problem request with invalid session id
invalid_session_id="when_invalid_must_have_status_code:401"
status_code=$(curl -s -o response.json \
    -w "%{http_code}" \
    -X GET $URL/problem \
    -H "accept: application/json" \
    -H "X-Session-ID: $invalid_session_id" )
echo "Problem(Invalid session id): HTTP Status Code = $status_code"
check_status_code $status_code 401 "get problem with invalid session id"

# Problem request with no session id
status_code=$(curl -s -o response.json \
    -w "%{http_code}" \
    -X GET $URL/problem \
    -H "accept: application/json")
echo "Problem Request(No session id): HTTP Status Code = $status_code"
check_status_code $status_code 401 "get problem with no session id"

# Submit solution
status_code=$(curl -s -o response.json \
    -w "%{http_code}" \
    -X POST $URL/solution \
    -H 'accept: application/json' \
    -H "X-Session-ID: $session_id" \
    -H 'Content-Type: application/json' \
    -d '{
    "problemId": "'"$problemId"'",
    "solutionCode": "my code"
}')
echo "Post Solution: HTTP Status Code = $status_code"
check_status_code $status_code 200 "post solution"

echo "All tests have passed!"

rm -f ./response.json
