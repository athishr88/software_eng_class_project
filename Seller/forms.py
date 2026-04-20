from django import forms

from .models import SellerProfile


class SellerWebhookForm(forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = ("webhook_url", "webhook_secret", "webhook_enabled")
        labels = {
            "webhook_url": "Webhook URL",
            "webhook_secret": "Webhook secret",
            "webhook_enabled": "Enable webhook",
        }
        help_texts = {
            "webhook_url": "HTTPS endpoint that receives POST requests when a buyer places an order for your books.",
            "webhook_secret": "Optional. If set, we send header X-Webhook-Signature (hex HMAC-SHA256 of the JSON body).",
            "webhook_enabled": "When enabled, we POST to your URL after each successful order that includes your inventory.",
        }
        widgets = {
            "webhook_url": forms.URLInput(
                attrs={"placeholder": "https://your-server.example/hooks/orders", "style": "width:100%;"}
            ),
            "webhook_secret": forms.TextInput(
                attrs={"placeholder": "Optional shared secret", "style": "width:100%;", "autocomplete": "off"},
            ),
        }

    def clean(self):
        cleaned = super().clean()
        enabled = cleaned.get("webhook_enabled")
        url = (cleaned.get("webhook_url") or "").strip()
        if enabled and not url:
            self.add_error(
                "webhook_url",
                "Webhook URL is required when webhooks are enabled.",
            )
        return cleaned
