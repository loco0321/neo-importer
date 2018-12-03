import mimetypes

from django.utils.safestring import mark_safe
from rest_framework import serializers

from neo_importer.exceptions import StopImporter
from neo_importer.models import FileUploadHistory


class NeoFileImporterSerializer(serializers.ModelSerializer):

    class Meta:
        model = FileUploadHistory
        fields = ('uploaded_file', 'id')

    def __init__(self, valid_extensions=None, user=None, *args, **kwargs):
        process_importer = kwargs.pop('process_importer', False)
        self.no_validate_file = kwargs.pop('no_validate_file', False)
        self.importer = kwargs.pop('importer', None)

        super(NeoFileImporterSerializer, self).__init__(*args, **kwargs)
        #
        self.valid_extensions = ['xls', 'xlsx']
        if process_importer or self.no_validate_file:
            self.fields['uploaded_file'].required = False

        else:
            self.fields['uploaded_file'].required = True

    def is_the_type_of_file_valid(self, filename):
        if not self.valid_extensions: # no validation
            return True
        for extension in self.valid_extensions:
            if filename.lower().endswith(extension.lower()):
                return True
        return False

    def validate_template(self, file_uploaded):
        if not self.no_validate_file:
            self.importer.validate_template(file_uploaded)

    def validate_uploaded_file(self, the_file):
        "It always accept zip files, but it validate the first file inside the zip file."
        filename = the_file.name
        # if len(filename) > 50:
        #     raise forms.ValidationError('The file name is too big')
        # if filename.endswith('zip'):
        #     data_source, filename = self.decompress(the_file)
        # else:

        data_source, filename = the_file, the_file.name
        if not self.is_the_type_of_file_valid(filename):
            raise serializers.ValidationError('Invalid file. Accepted files: %s' % ', '.join(self.valid_extensions))

        try:
            file_uploaded = data_source
            if file_uploaded and self.importer is not None:
                self.validate_template(file_uploaded)

            return file_uploaded
        except AttributeError:
            return None

        except StopImporter as e:
            raise serializers.ValidationError(mark_safe(e))

    # def decompress(self, zipped_file):
    #     "If this is a zip file it returns the first file inside the zip. Else it return the same file."
    #     try:
    #         # zip file
    #         zip_file = zipfile.ZipFile(zipped_file)
    #         internal_file_name = zip_file.namelist()[0]
    #         extension = os.path.splitext(internal_file_name)[1]
    #         try:
    #             content_type = mimetypes.types_map[extension]
    #         except KeyError:
    #             content_type = None
    #         the_file = SimpleUploadedFile(internal_file_name, zip_file.read(internal_file_name), content_type=content_type)
    #         return the_file, internal_file_name
    #     except zipfile.BadZipfile:
    #         # not zip file. We reset it and the rest is the default behavior
    #         zipped_file.seek(0)
    #         return zipped_file, zipped_file.name


class FileUploadHistorySerializer(serializers.ModelSerializer):
    params = serializers.SerializerMethodField()

    class Meta:
        model = FileUploadHistory
        fields = ('id', 'uploaded_file', 'state', 'original_filename', 'type',
                  'start_execution_timestamp', 'finish_execution_timestamp',
                  'notification_sent', 'params')

    def get_params(self, obj):

        return obj.get_form_params()