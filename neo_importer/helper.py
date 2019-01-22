import json

from neo_importer.models import FileUploadHistory


class NeoResultHelper(object):

    def __init__(self, *args, **kwargs):
        self.data = None
        self.columns_mapping = kwargs.pop('columns_mapping', {})
        self.grouped_fields = kwargs.pop('grouped_fields', {})        # Group in table
        self.grouped_fields_labels = self.grouped_fields.keys()
        self.ignored_elements = kwargs.pop('ignored_elements', {})
        self.columns_to_group = kwargs.pop('columns_to_group', {})
        self.file_upload_history = None
        if kwargs.get('file_upload_history'):
            from neo_importer.serializers import FileUploadHistorySerializer
            self.file_upload_history = dict(FileUploadHistorySerializer(instance=kwargs.pop('file_upload_history')).data)
        self.single_elements = self.get_single_elements()

    def get_columns_to_group_values(self, group):
        return [group.get(field_mapping, '') for field_mapping in self.columns_to_group.values()]

    def get_single_elements(self):
        aux_columns = self.columns_mapping.copy()

        for key in tuple(self.grouped_fields.keys()) + tuple(self.ignored_elements.keys()):
            del aux_columns[key]

        return aux_columns

    def load_from_json(self, encoded_data):
        if not self.data:
            self.data = FileUploadHistory.decode_data(encoded_data)
        return self.data

    def prepare_list_elements(self, group):
        grouped_data = []
        for field_mapping in self.grouped_fields.values():
            grouped_data.append([{'field': field_mapping, 'value': x} for x in group.get(field_mapping, '')])
        return zip(*grouped_data)
