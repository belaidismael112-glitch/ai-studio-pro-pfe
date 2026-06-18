import pytest

@pytest.mark.asyncio
async def test_credit_packages_and_balance(client):
    email = "credits@example.com"
    password = "StrongPassword123!"

    await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Credits User"
    })

    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = r.json()["access_token"]

    # Public packages
    r = await client.get("/api/v1/credits/packages")
    assert r.status_code == 200
    pkgs = r.json()
    assert isinstance(pkgs, list) and len(pkgs) >= 1

    # Auth balance
    r = await client.get("/api/v1/credits/balance", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    bal = r.json()
    assert "credits" in bal
