from django.db import ProgrammingError


class ImporterSite(object):
    name = 'importers'

    def __init__(self):
        self._registry = {}
        self._importers = {}

    def register(self, importer_key, importer):
        self._importers[importer_key] = importer

        try:
            if hasattr(importer, 'get_permission'):
                importer.get_permission()

        except ProgrammingError:
            print('Please Migrate first')

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

    def get_api_urls(self):
        urlpatterns = ()
        for importer_key, importer in self._importers.items():
            urlpatterns += importer.get_api_urls()

        return urlpatterns

    @property
    def api_urls(self):
        return self.get_api_urls(), 'admin', 'api_%s' % self.name

    def get_importers(self):
        return self._importers

importer_site = ImporterSite()
