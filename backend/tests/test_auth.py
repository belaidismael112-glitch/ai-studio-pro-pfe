import pytest

@pytest.mark.asyncio
async def test_register_login_and_me(client):
    email = "testuser@example.com"
    password = "StrongPassword123!"

    # Register
    r = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Test User"
    })
    assert r.status_code in (200, 201), r.text

    # Login
    r = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    token = data["access_token"]

    # Me
    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"] == email
