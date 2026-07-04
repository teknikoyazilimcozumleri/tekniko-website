"""
Custom account forms: social signup with required password.
"""
from django import forms

from allauth.socialaccount.forms import SignupForm as BaseSocialSignupForm

FORM_INPUT_CLASS = (
    "form-input"
)


class ContactForm(forms.Form):
    SERVICE_CHOICES = [
        ("", "Hizmet türünü seçin"),
        ("ai_engineering", "Yapay Zeka Mühendisliği"),
        ("software", "Yazılım Geliştirme"),
        ("data_analysis", "Veri Analizi"),
        ("consulting", "Danışmanlık"),
        ("other", "Diğer"),
    ]

    full_name = forms.CharField(
        label="Ad Soyad",
        max_length=120,
        widget=forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "autocomplete": "name"}),
    )
    email = forms.EmailField(
        label="E-posta",
        widget=forms.EmailInput(attrs={"class": FORM_INPUT_CLASS, "autocomplete": "email"}),
    )
    company = forms.CharField(
        label="Şirket",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "autocomplete": "organization"}),
    )
    phone = forms.CharField(
        label="Telefon",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "autocomplete": "tel"}),
    )
    service_type = forms.ChoiceField(
        label="Hizmet Türü",
        choices=SERVICE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": FORM_INPUT_CLASS}),
    )
    message = forms.CharField(
        label="Mesaj",
        widget=forms.Textarea(attrs={"class": FORM_INPUT_CLASS, "rows": 5}),
    )

    def clean_service_type(self):
        value = self.cleaned_data.get("service_type")
        if not value:
            return ""
        return value


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
