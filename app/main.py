from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from modules.auth import sign_up_user, login_user, get_user
from modules.chat import get_user_threads, get_thread_chats, create_thread, save_chat_message
from modules.llm import stream_openai, stream_gemini

app = FastAPI(title="Supabase LLM Chatbot API")

class AuthRequest(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    prompt: str
    thread_id: str
    provider: str = "openai"  # "openai" or "gemini"

class NewChatRequest(BaseModel):
    title: str = "New Chat"

@app.post("/signup")
async def signup(request: AuthRequest):
    try:
        response = await sign_up_user(request.email, request.password)
        if response.user:
            return {"message": "User created successfully", "user_id": response.user.id}
        raise HTTPException(status_code=400, detail="Signup failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login")
async def login(request: AuthRequest):
    try:
        response = await login_user(request.email, request.password)
        if response.session:
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "user_id": response.user.id
            }
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/new_chat")
async def new_chat(request: NewChatRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.split(" ")[1]
    try:
        user_res = await get_user(token)
        if not user_res.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        thread = await create_thread(user_res.user.id, request.title)
        if not thread:
            raise HTTPException(status_code=500, detail="Failed to create thread")
            
        return thread
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.split(" ")[1]
    try:
        # Verify user with Supabase
        user_res = await get_user(token)
        if not user_res.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        user_id = user_res.user.id
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")

    async def generate_and_save():
        full_response = ""
        
        if request.provider == "gemini":
            generator_func = stream_gemini(request.prompt)
        else:
            generator_func = stream_openai(request.prompt)
            
        async for chunk in generator_func:
            full_response += chunk
            yield chunk
            
        # Save persistence after stream is done
        await save_chat_message(user_id, request.thread_id, request.prompt, full_response)

    return StreamingResponse(generate_and_save(), media_type="text/event-stream")

@app.get("/threads")
async def get_threads(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.split(" ")[1]
    try:
        user_res = await get_user(token)
        if not user_res.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        user_id = user_res.user.id
        threads = await get_user_threads(user_id)
        return {"threads": threads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/threads/{thread_id}/chats")
async def get_chats(thread_id: str, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.split(" ")[1]
    try:
        user_res = await get_user(token)
        if not user_res.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        user_id = user_res.user.id
        # In a real app we might verify thread ownership here or rely on RLS
        chats = await get_thread_chats(user_id, thread_id)
        return {"chats": chats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
