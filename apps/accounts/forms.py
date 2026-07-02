"""
Custom account forms: social signup with required password.
"""
from django import forms

from allauth.socialaccount.forms import SignupForm as BaseSocialSignupForm


class SocialSignupForm(BaseSocialSignupForm):
    """
    Social (OAuth) signup form that requires password1/password2.
    Used when SOCIALACCOUNT_AUTO_SIGNUP is False so new users must set a password.
    """
    password1 = forms.CharField(
        label="Şifre",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        min_length=8,
    )
    password2 = forms.CharField(
        label="Şifre (tekrar)",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
    )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("İki şifre alanı eşleşmiyor.")
        return password2

    def save(self, request):
        user = super().save(request)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
