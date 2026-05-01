import pytest

@pytest.mark.django_db
def test_dashboard_loads(client, example_buyer):
    client.force_login(example_buyer)
    response = client.get("/buyer/dashboard/")
    assert response.status_code == 200

def test_dashboard_requires_login(client):
    response = client.get("/buyer/dashboard/")
    assert response.status_code == 302 
    assert "/login/" in response.url

@pytest.mark.django_db
def test_orders_loads(client, example_buyer):
    client.force_login(example_buyer)
    response = client.get("/buyer/orders/")
    assert response.status_code == 200

def test_orders_requires_login(client):
    response = client.get("/buyer/orders/")
    assert response.status_code == 302 
    assert "/login/" in response.url

@pytest.mark.django_db
def test_cart_loads(client, example_buyer):
    client.force_login(example_buyer)
    response = client.get("/buyer/cart/")
    assert response.status_code == 200

def test_cart_requires_login(client):
    response = client.get("/buyer/cart/")
    assert response.status_code == 302 
    assert "/login/" in response.url

@pytest.mark.django_db
def test_profile_loads(client, example_buyer):
    client.force_login(example_buyer)
    response = client.get("/buyer/profile/")
    assert response.status_code == 200

def test_profile_requires_login(client):
    response = client.get("/buyer/profile/")
    assert response.status_code == 302 
    assert "/login/" in response.url

@pytest.mark.django_db
def test_payments_loads(client, example_buyer):
    client.force_login(example_buyer)
    response = client.get("/buyer/checkout/payments/")
    assert response.status_code == 200

def test_payments_requires_login(client):
    response = client.get("/buyer/checkout/payments/")
    assert response.status_code == 302 
    assert "/login/" in response.url

@pytest.mark.django_db
def test_shipping_loads(client, example_buyer):
    client.force_login(example_buyer)
    response = client.get("/buyer/checkout/shipping/")
    assert response.status_code == 200

def test_shipping_requires_login(client):
    response = client.get("/buyer/checkout/shipping/")
    assert response.status_code == 302 
    assert "/login/" in response.url

@pytest.mark.django_db
def test_profile_loads(client, example_buyer):
    client.force_login(example_buyer)
    response = client.get("/buyer/profile/")
    assert response.status_code == 200

def test_profile_requires_login(client):
    response = client.get("/buyer/profile/")
    assert response.status_code == 302 
    assert "/login/" in response.url
