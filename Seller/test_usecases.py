import pytest

@pytest.mark.django_db
def test_seller_create_account():
    # Navigate to create account page

    # Provide account information

    # Login to account
    pass

@pytest.mark.django_db
def test_seller_login():
    # Navigate to and load login page

    # Provide email and password

    # Ensure seller dashboard has loaded
    pass

@pytest.mark.django_db
def test_seller_edits_email():
    # Navigate to account management

    # provide new email

    # ensure email has changed
    pass

@pytest.mark.django_db
def test_seller_add_book():
    # navigate to add books page

    # provide book information

    # navigate to inventory and ensure book is present
    pass

@pytest.mark.django_db
def test_seller_removes_book():
    # Navigate to inventory

    # Locate book in inventory

    # remove book from inventory
    pass

@pytest.mark.django_db
def test_seller_edits_book():
    # navigate to inventory

    # locate book in inventory

    # edit books' content
    pass

@pytest.mark.django_db
def test_seller_views_order():
    # naviate to orders

    # naviagate to specific order

    # ensure order information is present
    pass

@pytest.mark.django_db
def test_seller_views_sales():
    # naviagte to sales overview

    # view sales total

    # view indivdual sale item
    pass

@pytest.mark.django_db
def test_seller_views_inventory():
    # naviagte to inventory

    # ensure inventory items are present
    pass
