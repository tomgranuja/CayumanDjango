from django.conf import settings


def pytest_configure():
    """Set language to English for tests"""
    settings.LANGUAGE_CODE = "en"
