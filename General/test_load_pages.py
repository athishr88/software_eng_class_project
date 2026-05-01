import pytest

def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200

def test_catalog_loads(client):
    response = client.get("/catalog/")
    assert response.status_code == 200

def test_login_page_loads(client):
    response = client.get("/login/")
    assert response.status_code == 200

def test_registration_page_loads(client):
    response = client.get("/register/")
    assert response.status_code == 200
