from django.apps import AppConfig


class SmilesConfig(AppConfig):
    name = "smiles"
    verbose_name = "Smiles"

    def ready(self):
        # Import models to ensure they are registered properly
        from . import models  # noqa

        # Import signals to connect signal handlers
        from . import signals  # noqa
