# Supabase LLM Chatbot API Documentation

This API provides authentication via Supabase and streaming chat responses from OpenAI and Gemini.

## Base URL
`http://localhost:8000`

## Authentication
Most endpoints are public, but the `/chat` endpoint requires a valid Supabase access token passed in the `Authorization` header.

Header format:
`Authorization: Bearer <your_access_token>`

---

## Endpoints

### 1. User Signup
Create a new user account in Supabase.

*   **URL**: `/signup`
*   **Method**: `POST`
*   **Request Body**:
    ```json
    {
      "email": "user@example.com",
      "password": "yourpassword"
    }
    ```
*   **Success Response**:
    *   **Code**: 200 OK
    *   **Content**:
        ```json
        {
          "message": "User created successfully",
          "user_id": "uuid-string"
        }
        ```
*   **Error Response**:
    *   **Code**: 400 Bad Request (if email is invalid or signup fails)

### 2. User Login
Authenticate a user and receive access tokens.

*   **URL**: `/login`
*   **Method**: `POST`
*   **Request Body**:
    ```json
    {
      "email": "user@example.com",
      "password": "yourpassword"
    }
    ```
*   **Success Response**:
    *   **Code**: 200 OK
    *   **Content**:
        ```json
        {
          "access_token": "jwt-token-string",
          "refresh_token": "refresh-token-string",
          "user_id": "uuid-string"
        }
        ```
*   **Error Response**:
    *   **Code**: 401 Unauthorized (invalid credentials)

### 3. Create New Chat (Thread)
Create a new conversation thread.

*   **URL**: `/new_chat`
*   **Method**: `POST`
*   **Headers**:
    *   `Authorization: Bearer <access_token>`
*   **Request Body**:
    ```json
    {
      "title": "My New Chat"
    }
    ```
    *   `title`: Optional. Default is "New Chat".
*   **Success Response**:
    *   **Code**: 200 OK
    *   **Content**:
        ```json
        {
          "id": "thread-uuid",
          "user_id": "user-uuid",
          "title": "My New Chat",
          "created_at": "timestamp",
          "updated_at": "timestamp"
        }
        ```

### 4. Chat (Streaming)
Send a message to a thread and get a streaming response.

*   **URL**: `/chat`
*   **Method**: `POST`
*   **Headers**: 
    *   `Authorization: Bearer <access_token>`
*   **Request Body**:
    ```json
    {
      "prompt": "Tell me a joke.",
      "thread_id": "thread-uuid",
      "provider": "openai" 
    }
    ```
    *   `thread_id`: **Required**. The ID of the thread to post to.
    *   `provider`: Optional. Can be `"openai"` (default) or `"gemini"`.
*   **Success Response**:
    *   **Code**: 200 OK
    *   **Content-Type**: `text/event-stream`
    *   **Body**: A stream of text chunks.
*   **Error Response**:
    *   **Code**: 401 Unauthorized
    *   **Code**: 500 Internal Server Error

### 5. List Threads
Get all conversation threads for the user.

*   **URL**: `/threads`
*   **Method**: `GET`
*   **Headers**:
    *   `Authorization: Bearer <access_token>`
*   **Success Response**:
    *   **Code**: 200 OK
    *   **Content**:
        ```json
        {
          "threads": [
            {
              "id": "thread-uuid",
              "title": "My New Chat",
              "created_at": "timestamp",
              "updated_at": "timestamp"
            }
          ]
        }
        ```

### 6. Get Thread History
Get all chat messages for a specific thread.

*   **URL**: `/threads/{thread_id}/chats`
*   **Method**: `GET`
*   **Headers**:
    *   `Authorization: Bearer <access_token>`
*   **Success Response**:
    *   **Code**: 200 OK
    *   **Content**:
        ```json
        {
          "chats": [
            {
              "id": "chat-uuid",
              "query": "User prompt",
              "response": "AI response",
              "created_at": "timestamp"
            }
          ]
        }
        ```

### 7. Delete Thread
Delete a specific thread and all associated messages.

*   **URL**: `/threads/{thread_id}`
*   **Method**: `DELETE`
*   **Headers**:
    *   `Authorization: Bearer <access_token>`
*   **Success Response**:
    *   **Code**: 200 OK
    *   **Content**:
        ```json
        {
          "message": "Thread deleted successfully"
        }
        ```
*   **Error Response**:
    *   **Code**: 404 Not Found
    *   **Code**: 401 Unauthorized
    *   **Code**: 500 Internal Server Error
---

## Testing with cURL

### Signup
```bash
curl -X POST http://localhost:8000/signup \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "Password123!"}'
```

### Login
```bash
curl -X POST http://localhost:8000/login \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "Password123!"}'
```

### Create New Chat
```bash
curl -X POST http://localhost:8000/new_chat \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"title": "Test Chat"}'
```

### Chat
```bash
curl -X POST http://localhost:8000/chat \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Hi!", "thread_id": "<THREAD_ID>", "provider": "openai"}' \
     --no-buffer
```

### List Threads
```bash
curl -X GET http://localhost:8000/threads \
     -H "Authorization: Bearer <TOKEN>"
```


### Get Chats for Thread
```bash
curl -X GET http://localhost:8000/threads/<THREAD_ID>/chats \
     -H "Authorization: Bearer <TOKEN>"
```

### Delete Thread
```bash
curl -X DELETE http://localhost:8000/threads/<THREAD_ID> \
     -H "Authorization: Bearer <TOKEN>"
```

---

## Database Schema

### `threads` Table
| Column       | Type                     | Description |
|--------------|--------------------------|-------------|
| `id`         | `uuid` (PK)              | Unique thread ID |
| `user_id`    | `uuid` (FK)              | Reference to `auth.users` |
| `title`      | `text`                   | Title of the conversation |
| `created_at` | `timestamp with timezone`| Creation timestamp |
| `updated_at` | `timestamp with timezone`| Last update timestamp |

### `chat_history` Table
| Column       | Type                     | Description |
|--------------|--------------------------|-------------|
| `id`         | `uuid` (PK)              | Unique message ID |
| `thread_id`  | `uuid` (FK)              | Reference to `threads.id` |
| `query`      | `text`                   | User's message |
| `response`   | `text`                   | AI's response |
| `created_at` | `timestamp with timezone`| Timestamp of the message |
