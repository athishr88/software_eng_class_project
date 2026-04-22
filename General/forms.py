from django import forms
from django.contrib.auth import get_user_model  
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import make_password

User = get_user_model()
class ForgotPasswordEmailForm(forms.Form):
    email = forms.EmailField(label="Email", max_length=255)

SECURITY_QUESTION_CHOICES =[
    ("", "Select a security question"),
    ("What is your mother's maiden name?", "What is your mother's maiden name?"),
    ("What was the name of your first pet?", "What was the name of your first pet?"),
    ("In what city were you born?", "In what city were you born?"),
]

class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput())
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput())

    security_question = forms.ChoiceField(label="Security Question", choices=SECURITY_QUESTION_CHOICES)
    security_answer = forms.CharField(label="Security Question Answer", max_length=255, widget=forms.TextInput())

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone", "role", "security_question", "security_answer"]

    def clean(self):
        cleaned_data = super().clean()
        pw1 = cleaned_data.get("password1")
        pw2 = cleaned_data.get("password2")

        if pw1 and pw2 and pw1 != pw2:
            self.add_error("password2", "Passwords do not match.")
    
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.security_question = self.cleaned_data["security_question"]
        user.security_answer_hash = make_password(self.cleaned_data["security_answer"].strip().lower())
        if commit:
            user.save()
        return user
    
class SecurityQuestionForm(forms.Form):
    security_question = forms.ChoiceField(label="Security Question", choices=SECURITY_QUESTION_CHOICES)
    security_answer = forms.CharField(label="Security Question Answer", max_length=255, widget=forms.TextInput())

    def clean_security_answer(self):
        answer = self.cleaned_data["security_answer"].strip().lower()
        if not answer:
            raise forms.ValidationError("security answer required.")
        return answer

class SecurityQuestionResetForm(forms.Form):
    answer = forms.CharField(label="Security Question Answer", max_length=255)
    new_password1 = forms.CharField(label="New Password", widget=forms.PasswordInput)
    new_password2 = forms.CharField(label="Confirm New Password", widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        pw1 = cleaned_data.get("new_password1")
        pw2 = cleaned_data.get("new_password2")

        if pw1 and pw2 and pw1 != pw2:
            self.add_error("new_password2", "Passwords do not match.")
        
        if pw1:
            validate_password(pw1)
        
        return cleaned_data
            