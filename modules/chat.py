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
        # First verify thread ownership (optional but good security practice, 
        # though RLS should handle it if set up correctly. We'll do a join or check first).
        # Depending on RLS, simple select on chat_history with thread_id might be enough 
        # if chat_history also has user_id and RLS checks it. 
        # Use simpler approach assuming user can only access their own data via RLS or filter.
        
        response = supabase.table("chat_history").select("id, query, response, created_at").eq("thread_id", thread_id).eq("user_id", user_id).order("created_at", desc=False).execute()
        return response.data
    except Exception as e:
        print(f"Error fetching chats: {e}")
        return []
