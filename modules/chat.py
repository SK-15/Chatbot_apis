from modules.database import supabase

async def get_user_threads(user_id: str):
    """
    Fetch all threads for a specific user, ordered by most recently updated.
    """
    try:
        response = supabase.table("threads").select("id, title, created_at, updated_at").eq("user_id", user_id).order("updated_at", desc=True).execute()
        return response.data
    except Exception as e:
        print(f"Error fetching threads: {e}")
        return []

async def get_thread_chats(user_id: str, thread_id: str):
    """
    Fetch all chat messages for a specific thread.
    Ensures the thread belongs to the user.
    """
    try:
        # First verify thread ownership
        thread_response = supabase.table("threads").select("id").eq("id", thread_id).eq("user_id", user_id).execute()
        
        if not thread_response.data:
            # Thread doesn't exist or doesn't belong to the user
            return []
        
        # Fetch chats for the verified thread
        response = supabase.table("chat_history").select("id, query, response, created_at").eq("thread_id", thread_id).order("created_at", desc=False).execute()
        return response.data
    except Exception as e:
        print(f"Error fetching chats: {e}")
        return []

async def create_thread(user_id: str, title: str = "New Chat"):
    """
    Create a new thread for the user.
    """
    try:
        response = supabase.table("threads").insert({
            "user_id": user_id,
            "title": title
        }).execute()
        
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error creating thread: {e}")
        return None

async def save_chat_message(user_id: str, thread_id: str, prompt: str, response: str):
    """
    Save the user prompt and AI response to the database.
    Also update the thread's updated_at timestamp.
    """
    try:
        # Save chat message
        supabase.table("chat_history").insert({
            # user_id is not in the schema anymore
            "thread_id": thread_id,
            "query": prompt,
            "response": response
        }).execute()

        # Update thread timestamp
        supabase.table("threads").update({
            "updated_at": "now()"
        }).eq("id", thread_id).execute()

        return True
    except Exception as e:
        print(f"Error saving chat: {e}")
        return False
