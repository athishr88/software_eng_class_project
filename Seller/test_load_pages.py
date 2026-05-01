import pytest

# dashboard
@pytest.mark.django_db
def test_dashboard_loads(client, example_seller):
    client.force_login(example_seller)
    response = client.get("/seller/dashboard/")
    assert response.status_code == 200

def test_dashboard_requires_login(client):
    response = client.get("/seller/dashboard/")
    assert response.status_code == 302 
    assert "/login/" in response.url
    
# profile
@pytest.mark.django_db
def test_profile_loads(client, example_seller):
    client.force_login(example_seller)
    response = client.get("/seller/profile/")
    assert response.status_code == 200

def test_profile_requires_login(client):
    response = client.get("/seller/profile/")
    assert response.status_code == 302 
    assert "/login/" in response.url
    
# sales
@pytest.mark.django_db
def test_sales_overview_loads(client, example_seller):
    client.force_login(example_seller)
    response = client.get("/seller/dashboard/")
    assert response.status_code == 200

def test_sales_overview_requires_login(client):
    response = client.get("/seller/dashboard/")
    assert response.status_code == 302 
    assert "/login/" in response.url
    
# orders
@pytest.mark.django_db
def test_orders_loads(client, example_seller):
    client.force_login(example_seller)
    response = client.get("/seller/dashboard/sales-overview/")
    assert response.status_code == 200

def test_orders_requires_login(client):
    response = client.get("/seller/dashboard/sales-overview/")
    assert response.status_code == 302 
    assert "/login/" in response.url
    
# returns
@pytest.mark.django_db
def test_returns_loads(client, example_seller):
    client.force_login(example_seller)
    response = client.get("/seller/returns/")
    assert response.status_code == 200

def test_returns_requires_login(client):
    response = client.get("/seller/returns/")
    assert response.status_code == 302 
    assert "/login/" in response.url
    
# inventory
@pytest.mark.django_db
def test_inventory_loads(client, example_seller):
    client.force_login(example_seller)
    response = client.get("/seller/inventory/")
    assert response.status_code == 200

def test_inventory_requires_login(client):
    response = client.get("/seller/inventory/")
    assert response.status_code == 302 
    assert "/login/" in response.url
    
# add book
@pytest.mark.django_db
def test_add_book_loads(client, example_seller):
    client.force_login(example_seller)
    response = client.get("/seller/inventory/add/")
    assert response.status_code == 200

def test_add_book_requires_login(client):
    response = client.get("/seller/inventory/add/")
    assert response.status_code == 302 
    assert "/login/" in response.url
