from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UsernameField
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class StudentLoginForm(AuthenticationForm):
    username = UsernameField(
        label=_("RUT"),
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
        help_text=_("Use dash, no point, lowercase (ex. 23456789-k)"),
    )
    password = forms.CharField(label=_("Password"), strip=False, widget=forms.PasswordInput(attrs={"class": "form-control"}))

    def get_invalid_login_error(self):
        return ValidationError(
            self.error_messages["invalid_login"],
            code="invalid_login",
            params={"username": _("RUT")},
        )
