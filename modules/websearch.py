import asyncio
from typing import List, Dict
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup
from modules.llm import generate_response

async def decompose_query(user_query: str) -> List[str]:
    """
    Decompose a complex query into smaller, meaningful sub-queries using LLM.
    """
    prompt = f"""
    You are a helpful assistant. Break down the following user query into a list of 2-3 specific search queries that would help answer the original request comprehensively.
    Return ONLY a list of queries separated by newlines. No numbering or bullets. Do NOT use double quotes around the queries.
    
    User Query: "{user_query}"
    """
    response = await generate_response(prompt)
    if not response:
        return [user_query]
    
    queries = [q.strip().strip('"') for q in response.split('\n') if q.strip()]
    return queries if queries else [user_query]

def perform_search(query: str, num_results: int = 3) -> List[Dict]:
    """
    Perform a search using DuckDuckGo (via ddgs) and return a list of results.
    """
    try:
        results = []
        # ddgs text search
        # returns iterator of dicts: {'title':..., 'href':..., 'body':...}
        ddg_results = DDGS().text(query, max_results=num_results)
        
        for r in ddg_results:
             results.append({
                 "title": r.get('title'),
                 "link": r.get('href'),
                 "description": r.get('body')
             })
        return results
    except Exception as e:
        print(f"Error performing search for '{query}': {e}")
        return []

def scrape_content(url: str) -> str:
    """
    Fetch and extract text content from a URL.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text(separator=' ', strip=True)
        # basic cleanup
        text = ' '.join(text.split())
        return text[:2000] # Limit content length
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return ""

async def get_relevant_answer(user_query: str, search_results: List[Dict]) -> str:
    """
    Synthesize an answer from search results using LLM.
    """
    context = ""
    for res in search_results:
        context += f"Source: {res.get('title', 'Unknown')} ({res['link']})\n"
        context += f"Description: {res.get('description', '')}\n"
        if 'content' in res:
             context += f"Content: {res['content']}\n"
        context += "---\n"
        
    prompt = f"""
    Answer the user query based ONLY on the provided search results.
    Cite the sources if possible.
    
    User Query: "{user_query}"
    
    Search Results:
    {context}
    """
    
    return await generate_response(prompt)

async def web_search_task(user_query: str):
    """
    Orchestrate the full web search handling.
    """
    # 1. Decompose
    sub_queries = await decompose_query(user_query)
    print(f"Sub-queries: {sub_queries}")
    
    all_results = []
    
    # 2. Search for each sub-query
    for q in sub_queries:
        print(f"Searching for: {q}")
        results = perform_search(q, num_results=2)
        all_results.extend(results)
        
    # Deduplicate by link
    unique_links = set()
    unique_results = []
    for r in all_results:
        if r['link'] not in unique_links:
            unique_links.add(r['link'])
            unique_results.append(r)
    
    # 3. Scrape content (select top 3 from unique results)
    final_results = []
    for res in unique_results[:3]: 
        print(f"Scraping: {res['link']}")
        content = scrape_content(res['link'])
        res['content'] = content
        final_results.append(res)
        
    # 4. Generate Answer
    answer = await get_relevant_answer(user_query, final_results)
    return answer
