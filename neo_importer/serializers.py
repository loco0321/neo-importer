import mimetypes

from django.utils.safestring import mark_safe
from rest_framework import serializers

from neo_importer.exceptions import StopImporter
from neo_importer.models import FileUploadHistory


class NeoFileImporterSerializer(serializers.Serializer):
    uploaded_file = serializers.FileField()

    id = serializers.IntegerField(read_only=True)

    def __init__(self, valid_extensions=None, user=None, *args, **kwargs):
        process_importer = kwargs.pop('process_importer', False)
        self.no_validate_file = kwargs.pop('no_validate_file', False)
        self.importer = kwargs.pop('importer', None)
        self.valid_extensions = valid_extensions or ['xls', 'xlsx']
        self.user = user

        super(NeoFileImporterSerializer, self).__init__(*args, **kwargs)

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

    def save(self, **kwargs):
        file_upload_history = FileUploadHistory.objects.create(
            uploaded_file=self.validated_data.get('uploaded_file'),
        )
        return file_upload_history


class FileUploadHistorySerializer(serializers.ModelSerializer):
    params = serializers.SerializerMethodField()

    class Meta:
        model = FileUploadHistory
        fields = ('id', 'uploaded_file', 'state', 'original_filename', 'type',
                  'start_execution_timestamp', 'finish_execution_timestamp',
                  'notification_sent', 'params', 'validate_end', 'celery_tasks')

    def get_params(self, obj):
        return obj.get_form_params()
