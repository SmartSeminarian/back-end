# Smart Seminarian API Documentation

## Overview
Smart Seminarian API is designed to help users train basic C programming skills. This documentation provides an overview of the available endpoints and how to use them.

### API Information
- **Title:** Smart Seminarian API
- **Description:** API for the Smart Seminarian project to help users train basic C programming skills.
- **Version:** 1.0.0

### Servers
- **Production Server:** todo
### Endpoints

#### User Management

- **User Login**
  - **Endpoint:** `/login`
  - **Method:** POST
  - **Summary:** User login
  - **Request Body:**
    ```json
    {
      "username": "string",
      "password": "string"
    }
    ```
  - **Responses:**
    - `200`: Successful login
      ```json
      {
        "token": "string"
      }
      ```

- **Get User Profile**
  - **Endpoint:** `/profile`
  - **Method:** GET
  - **Summary:** Get user profile
  - **Responses:**
    - `200`: User profile data
      ```json
      {
        "username": "string",
        "trainingData": [
          {
            "concept": "string",
            "status": "string"
          }
        ]
      }
      ```

#### Training and Problem Solving

- **Get Next Concept Recommendation**
  - **Endpoint:** `/commendation`
  - **Method:** GET
  - **Summary:** Get next concept recommendation
  - **Responses:**
    - `200`: Recommended concept
      ```json
      {
        "concept": "string"
      }
      ```

- **Get Concept Description**
  - **Endpoint:** `/concept/{name}`
  - **Method:** GET
  - **Summary:** Get concept description
  - **Parameters:**
    - `name` (path, required): Concept name
  - **Responses:**
    - `200`: Concept details
      ```json
      {
        "name": "string",
        "motivation": "string",
        "description": "string",
        "example": "string",
        "links": ["string"],
        "analogies": "string"
      }
      ```

- **Get Problem to Solve**
  - **Endpoint:** `/problem`
  - **Method:** GET
  - **Summary:** Get problem to solve
  - **Responses:**
    - `200`: Problem details
      ```json
      {
        "id": "string",
        "description": "string",
        "exampleInput": "string",
        "exampleOutput": "string"
      }
      ```

- **Submit Solution**
  - **Endpoint:** `/solution`
  - **Method:** POST
  - **Summary:** Submit solution
  - **Request Body:**
    ```json
    {
      "problemId": "string",
      "solutionCode": "string"
    }
    ```
  - **Responses:**
    - `200`: Solution submission response
      ```json
      {
        "feedback": "string"
      }
      ```

- **Get Additional Explanation**
  - **Endpoint:** `/explanation/{type}`
  - **Method:** GET
  - **Summary:** Get additional explanation
  - **Parameters:**
    - `type` (path, required): Type of explanation (concept, problem, compilation, autoGrading)
    - `reference` (query, required): Reference for explanation
  - **Responses:**
    - `200`: Explanation details
      ```json
      {
        "explanation": "string"
      }
      ```

- **Provide Feedback**
  - **Endpoint:** `/feedback`
  - **Method:** POST
  - **Summary:** Provide feedback
  - **Security:** Bearer Auth
  - **Request Body:**
    ```json
    {
      "type": "string",
      "content": "string"
    }
    ```
  - **Responses:**
    - `200`: Feedback submission response
      ```json
      {
        "status": "string"
      }
      ```

