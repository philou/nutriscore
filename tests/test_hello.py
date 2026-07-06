from fastapi.testclient import TestClient

from nutriscore.main import app

client = TestClient(app)


def test_hello_returns_hello_world():
    response = client.get("/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "hello world"}
