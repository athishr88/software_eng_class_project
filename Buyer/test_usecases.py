import pytest

@pytest.mark.django_db
def test_buyer_create_account():
    # Navigate to create account page

    # Provide account information

    # Login to account
    pass

@pytest.mark.django_db
def test_buyer_login():
    # Navigate to and load login page

    # Provide email and password

    # Ensure buyer dashboard has loaded
    pass

@pytest.mark.django_db
def test_buyer_edits_email():
    # Navigate to account management

    # provide new email

    # ensure email has changed
    pass

@pytest.mark.django_db
def test_buyer_edits_shipping_address():
    # Navigate to shipping address page

    # provide shipping addres

    # ensure shipping address has been added
    pass

@pytest.mark.django_db
def test_buyer_edits_payment():
    # Navigate to payment methods page

    # provide payment method

    # ensure payment method has been added
    pass

@pytest.mark.django_db
def test_buyer_add_book_to_cart():
    # navigate to catalog

    # add book to cart

    # naviagate to cart

    # ensure book is in cart
    pass

@pytest.mark.django_db
def test_buyer_checkout():
    # add book to cart

    # add shipping address

    # add payment method

    # place order

    # ensure order is present
    pass

@pytest.mark.django_db
def test_buyer_view_order():
    # naviage to orders

    # view exisitng order
    pass

@pytest.mark.django_db
def test_buyer_request_return():
    # navigate to existing order

    # request a return
    pass