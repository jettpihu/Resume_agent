import json
import httpx

async def fetch_user_data(query: str) -> str:
    """
    Fetches profile data. Integrates with the real GitHub REST API.
    LeetCode and LinkedIn are mocked or basic fallback.
    """
    try:
        if "github.com/" in query:
            username = query.split("github.com/")[1].split()[0]
            # Real GitHub API fetch
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://api.github.com/users/{username}")
                if resp.status_code == 200:
                    data = resp.json()
                    return json.dumps({
                        "platform": "GitHub",
                        "username": username,
                        "name": data.get("name"),
                        "followers": data.get("followers", 0),
                        "public_repos": data.get("public_repos", 0),
                        "bio": data.get("bio", "No bio available")
                    }, indent=2)
                else:
                    return f"GitHub fetch failed. Status: {resp.status_code}"
        elif "leetcode.com/" in query:
            return json.dumps({
                "platform": "LeetCode",
                "problems_solved": 320,
                "ranking": 45000,
                "skills": ["Algorithms", "Data Structures", "Dynamic Programming"]
            })
        else:
            return "Profile data extracted from query context."
    except Exception as e:
        return f"Fetch Error: {e}"
    
    return "Profile data extracted from query context."
