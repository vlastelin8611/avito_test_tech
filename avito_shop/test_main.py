import pytest
from fastapi.testclient import TestClient
from main import app, Base, engine

@pytest.fixture(scope="module")
def test_client():
    # Перед тестами создаем таблицы, а после – удаляем
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(bind=engine)

def get_auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

def authenticate(client: TestClient, username: str, password: str = "dummy") -> str:
    response = client.post("/api/auth", json={"username": username, "password": password})
    assert response.status_code == 200
    token = response.json()["token"]
    return token

def test_buy_item(test_client: TestClient):
    token = authenticate(test_client, "testuser")
    headers = get_auth_header(token)
    # Покупаем t-shirt (стоимость 80)
    response = test_client.get("/api/buy/t-shirt", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 1000 - 80

def test_send_coin(test_client: TestClient):
    # Регистрируем двух пользователей: alice и bob
    token_alice = authenticate(test_client, "alice")
    token_bob = authenticate(test_client, "bob")
    headers_alice = get_auth_header(token_alice)
    headers_bob = get_auth_header(token_bob)

    # Alice переводит 200 монет Bob
    response = test_client.post("/api/sendCoin", json={"toUser": "bob", "amount": 200}, headers=headers_alice)
    assert response.status_code == 200
    data = response.json()
    # Баланс Alice должен уменьшиться
    assert data["balance"] == 1000 - 200

    # Проверяем, что у Bob баланс увеличился через /api/info
    response = test_client.get("/api/info", headers=headers_bob)
    info = response.json()
    # Начальный баланс Bob был 1000, плюс 200 = 1200
    assert info["coins"] == 1200
