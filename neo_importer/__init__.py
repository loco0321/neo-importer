from django.utils.module_loading import autodiscover_modules

from neo_importer.sites import ImporterSite, importer_site


def autodiscover():
    """
    Auto-discover INSTALLED_APPS admin.py modules and fail silently when
    not present. This forces an import on them to register any admin bits they
    may want.
    """

    autodiscover_modules('importers', register_to=importer_site)