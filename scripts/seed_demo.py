import httpx

client = httpx.Client(base_url="http://127.0.0.1:7337/api/v1")

s1 = client.post(
    "/sessions",
    json={"title": "Implement JWT rotation", "provider": "openai", "model": "gpt-5.6-terra"},
).json()

s2 = client.post(
    "/sessions",
    json={"title": "Security validation & fuzzing", "provider": "copilot", "model": "gpt-5.4"},
).json()

s3 = client.post(
    "/sessions",
    json={
        "title": "Explore token revocation DB",
        "provider": "bedrock",
        "model": "anthropic.claude-3-5-sonnet",
    },
).json()

# Handoff from builder to validator
client.post(
    f"/sessions/{s1['id']}/handoffs",
    json={
        "target_session_id": s2["id"],
        "kind": "review",
        "summary": "Review JWT token rotation and replay protection.",
    },
)

# Overlap between builder and explorer
client.post(
    f"/sessions/{s1['id']}/overlaps",
    json={
        "target_session_id": s3["id"],
        "kind": "code",
        "score": 0.85,
        "evidence": "Both sessions touch src/auth/token_store.py and schema.",
        "inferred": False,
    },
)

# Compaction on builder session
client.post(
    f"/sessions/{s1['id']}/compactions",
    json={
        "objective": "Implement secure JWT refresh token rotation",
        "completed": "Added rotation middleware and revocation schema",
        "active": "Testing edge cases and expiration logic",
        "blocked": "(none)",
        "next_move": "Run pytest suite with validator feedback",
        "relevant_files": "src/auth/jwt.py, src/auth/token_store.py",
        "tokens_saved": 42500,
    },
)

print("Demo session graph populated successfully!")
