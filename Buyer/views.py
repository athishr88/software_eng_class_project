from django.shortcuts import render


def home(request):
    """Placeholder: Buyer home / catalog."""
    return render(request, "Buyer/home/index.html")

