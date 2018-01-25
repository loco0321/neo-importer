import mimetypes
import os
import zipfile

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.safestring import mark_safe

from neo_importer.exceptions import StopImporter
from neo_importer.models import FileUploadHistory


class FileImporterForm(forms.ModelForm):

    class Meta:
        model = FileUploadHistory
        fields = ('uploaded_file',)

    def __init__(self, valid_extensions=None, user=None, *args, **kwargs):
        # Init form
        # if not hasattr(self, 'helper'):
        #     self.helper = FormHelper()
        #     self.helper.form_tag = False
        #     self.helper.layout = Layout(
        #         Field('uploaded_file',template='zina_forms/bs3_file_field.html'),
        #         Field('action', template='zina_forms/simple_field.html', css_class='form-control'),
        #         Field('customer_team', template='zina_forms/simple_field.html', css_class='form-control'),
        #         Field('reason', template='zina_forms/simple_field.html', css_class='form-control'),
        #         Field('cancel_related_proposal_materials', template='zina_forms/bs3_checkbox_field_modified.html'),
        #     )
        super(FileImporterForm, self).__init__(*args, **kwargs)
        # Add validations
        self.valid_extensions = valid_extensions or []
        self.user = user
        # Properties file field imput
        self.fields['uploaded_file'].widget.attrs = {
            'class': 'form-control',
            'multiple': 'true',
            'data-preview-file-type': 'any',
            'data-initial-caption': 'Upload '+','.join(self.valid_extensions)+' file here',
        }
        # Custom label
        # self.fields['uploaded_file'].label = u'<label class="control-label">uploaded_file</label><label class="mandatory">*</label>'
        # required field
        self.fields['uploaded_file'].required = True

    def is_the_type_of_file_valid(self, filename):
        if not self.valid_extensions: # no validation
            return True
        for extension in self.valid_extensions:
            if filename.lower().endswith(extension.lower()):
                return True
        return False

    def decompress(self, zipped_file):
        "If this is a zip file it returns the first file inside the zip. Else it return the same file."
        try:
            # zip file
            zip_file = zipfile.ZipFile(zipped_file)
            internal_file_name = zip_file.namelist()[0]
            extension = os.path.splitext(internal_file_name)[1]
            try:
                content_type = mimetypes.types_map[extension]
            except KeyError:
                content_type = None
            the_file = SimpleUploadedFile(internal_file_name, zip_file.read(internal_file_name), content_type=content_type)
            return the_file, internal_file_name
        except zipfile.BadZipfile:
            # not zip file. We reset it and the rest is the default behavior
            zipped_file.seek(0)
            return zipped_file, zipped_file.name

    def clean_uploaded_file(self):
        "It always accept zip files, but it validate the first file inside the zip file."
        the_file = self.cleaned_data['uploaded_file']
        filename = the_file.name
        # if len(filename) > 50:
        #     raise forms.ValidationError('The file name is too big')
        if filename.endswith('zip'):
            data_source, filename = self.decompress(the_file)
        else:
            data_source, filename = the_file, the_file.name
        if not self.is_the_type_of_file_valid(filename):
            raise forms.ValidationError('Invalid file. Accepted files: %s' % ', '.join(self.valid_extensions))
        return data_source


class NeoFileImporterForm(FileImporterForm):
    def __init__(self, valid_extensions=None, user=None, *args, **kwargs):
        process_importer = kwargs.pop('process_importer', False)
        self.no_validate_file = kwargs.pop('no_validate_file', False)
        self.importer = kwargs.pop('importer', None)
        super(NeoFileImporterForm, self).__init__(valid_extensions, user, *args, **kwargs)
        if process_importer or self.no_validate_file:
            self.fields['uploaded_file'].required = False

    def validate_template(self, file_uploaded):
        if not self.no_validate_file:
            self.importer.validate_template(file_uploaded)

    def clean_uploaded_file(self):
        "It always accept zip files, but it validate the first file inside the zip file."
        try:
            file_uploaded = super(NeoFileImporterForm, self).clean_uploaded_file()
            if file_uploaded and self.importer is not None:
                self.validate_template(file_uploaded)

            return file_uploaded
        except AttributeError:
            return None

        except StopImporter as e:
            raise ValidationError(mark_safe(e))