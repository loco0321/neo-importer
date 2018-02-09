class ImporterSite(object):
    name = 'importers'

    def __init__(self):
        self._registry = {}
        self._importers = {}

    def register(self, importer_key, importer):
        self._importers[importer_key] = importer

        if hasattr(importer, 'get_permission'):
            importer.get_permission()

    def get_importer(self, importer_key):
        return self._importers.get(importer_key)

    def get_urls(self):
        from django.conf.urls import url, include
        urlpatterns = ()
        for importer_key, importer in self._importers.items():
            urlpatterns += importer.get_urls()

        return urlpatterns

    @property
    def urls(self):
        return self.get_urls(), 'admin', self.name

    def get_importers(self):
        return self._importers

importer_site = ImporterSite()
