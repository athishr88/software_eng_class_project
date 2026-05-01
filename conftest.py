import pytest
from General.models import User, Address

@pytest.fixture
def example_buyer():
    return User.objects.create(
        role='Buyer',
        email='buyer_email@testemail.com',
        password='testpassword',
        first_name='Buyer',
        last_name='Test',
        buyer_approved=True,
    )

@pytest.fixture
def example_seller():
    return User.objects.create(
        role='Buyer',
        email='buyer_email@testemail.com',
        password='testpassword',
        first_name='Buyer',
        last_name='Test',
        buyer_approved=True,
        seller_approved=True,
    )

@pytest.fixture
def buyer_address(example_buyer):
    return Address.objects.create(
        user=example_buyer,
        line1='1204 Example Street',
        line2='Example apt',
        city='Example City',
        state='EX',
        postal_code='12345',
        country='US',
    )

@pytest.fixture
def seller_address(example_seller):
    return Address.objects.create(
        user=example_seller,
        line1='1204 Example Street',
        line2='Example apt',
        city='Example City',
        state='EX',
        postal_code='12345',
        country='US',
    )
