Neo Importer
=================

Neo Importer application


HOW TO USE
----------

Then add this to your settings:

    INSTALLED_APPS = (
        # ...
        'neo_importer',
        # ...
    )

In main_app.urls add lines:

    import neo_importer

    neo_importer.autodiscover()


    urlpatterns = [
        # ...
        url('', neo_importer.importer_site.urls),
        # ...
    ]



For Create new importers add in importers file for each app "importers.py".

    from neo_importer import importer_site
    from neo_importer.core import GroupNeoImporterWithRevision

    class ExampleImporter(GroupNeoImporterWithRevision):

        def __init__(self, *args, **kwargs):
            self.columns_mapping = (
                {
                    'label': 'Example Label',
                    'field_mapping': 'example_label',       # Optional
                    'required': True,                       # Optional Default is required
                    'validators': []                        # Use Django Validators or custom validators
                    'index_to_group': False                 # Optional Default False. this field used for group multiple lines
                    'grouped_field': False                  # Optional Default False. this field used for allow multiple values for grouped lines

                },
            )

        def save_process_importer(self, cleaned_data):
            # Function to save data
            pass

    importer_site.register('importer_example_key', ExampleImporter)

For get menu in templates

    {% load neo_importer_extras %}
    {% generate_importer_link user 'importer_example_key' %}
