import json
import os

from datetime import datetime, timedelta
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete

from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as u


def content_file_name(instance, filename):
    file_name, file_extension = os.path.splitext(filename)
    filename = slugify(file_name)[:65] + file_extension
    TODAY = datetime.today()
    return '/'.join(['file_upload_history', str(TODAY.year), str(TODAY.month), filename])


class FileUploadHistoryManager(models.Manager):

    def for_user(self, user, type=None):
        qs = self.filter(user=user)
        if type:
            qs = qs.filter(type=type)
        return qs


class FileUploadHistory(models.Model):
    ENQUEUED = u'Enqueued'
    PROCESSING = u'Processing'
    PROCESSED = u'Processed'
    FAILED = u'Failed'

    STATE_CHOICES = (
            (ENQUEUED, ENQUEUED),
            (PROCESSING, PROCESSING),
            (PROCESSED, PROCESSED),
            (FAILED, FAILED),
    )

    type = models.CharField(max_length=50)
    # uploaded_file max_length=100. Filename must have maximum of 73 chars (100 - 27 = 73)
    uploaded_file = models.FileField(upload_to=content_file_name)

    # if zina_compatible:
    #     from django.contrib.auth.models import User
    #     user_model = User
    #
    # else:
    #     pass
        # user_model = get_user_model() TODO: Fix import
    # When user is None, the instance was created by scripts etc.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='file_upload_history', on_delete=models.SET_NULL)

    # Execution attributes
    results = models.TextField(blank=True)
    state = models.CharField(max_length=16, null=True, blank=True, choices=STATE_CHOICES)
    upload_timestamp = models.DateTimeField(auto_now_add=True)  # upload_time
    start_execution_timestamp = models.DateTimeField(null=True, blank=True, default=None)
    finish_execution_timestamp = models.DateTimeField(null=True, blank=True, default=None)
    notification_sent = models.NullBooleanField(default=False)
    original_filename = models.CharField(max_length=100, null=True, blank=True, default=None)

    form_params = models.TextField(blank=True, null=True)

    objects = FileUploadHistoryManager()

    sheet_importers = models.ManyToManyField('neo_importer.FileUploadHistory', null=True, blank=True, verbose_name=u('sheet importers'))

    # class Meta:
    #     db_table = 'data_importer_fileuploadhistory'

    def __unicode__(self):
        return '[%s] %s' % (str(self.upload_timestamp), self.type)

    def duration(self):
        "Duration includes the time the task is waiting in celery to be processed."
        if not self.finish_execution_timestamp or not self.start_execution_timestamp:
            return timedelta(0)
        return self.finish_execution_timestamp - self.start_execution_timestamp

    def is_processed(self):
        return self.state == self.PROCESSED

    def results_as_html(self):
        return mark_safe('<p>%s</p>' % self.results.replace('\n', '<br/>'))

    def file_link(self):
        if self.uploaded_file and os.path.exists(self.uploaded_file.path):
            _url = reverse('data_importer:download_file', args=[self.id, ])
            return "<a href='%s'>Download</a>" % _url
        else:
            return 'No attachment'

    file_link.allow_tags = True

    def save(self, *args, **kwargs):
        if self.original_filename is None and self.uploaded_file:
            self.original_filename = self.uploaded_file.name
        super(FileUploadHistory, self).save()

    def decode_results(self):
        import zlib, base64
        try:
            data = zlib.decompress(base64.b64decode(self.results))
            data = json.loads(data)
        except ValueError:
            data = {}

        return data

    def encode_data(self, data):
        import zlib, base64
        if not isinstance(data, str):
            data = json.dumps(data, default=lambda o: o.__dict__)

        try:
            data = zlib.compress(bytearray(data, encoding='UTF-8'), 9)
        except:
            data = zlib.compress(data, 9)
        return base64.b64encode(data)

    def decode_data(self, data):
        import zlib, base64
        try:
            data = zlib.decompress(base64.b64decode(data)).decode('utf-8')
            data = json.loads(data)
        except ValueError:
            data = {}

        return data

    def get_form_params(self):
        return self.decode_data(self.form_params)

    def set_form_params(self, data):
        form_params = self.encode_data(data)
        if (type(form_params).__name__ == 'bytes'):
            form_params = form_params.decode()
        self.form_params = form_params

    # def get_type_flowbot(self):
    #     from flowbot.models import Transaction
    #     try:
    #         types = self.type.split('-')
    #
    #         if len(types) > 1:
    #             transaction = Transaction.objects.get(name=types[1])
    #             return transaction.complete_name
    #
    #     except Transaction.DoesNotExist:
    #         pass
    #
    #     except Exception:
    #         pass
    #
    #     return self.type


def delete_filefield(sender, instance, **kwargs):
    """Automatically deleted files when records removed.
    """
    if hasattr(settings, 'DATA_IMPORTER_HISTORY') and settings.DATA_IMPORTER_HISTORY == False:
        print ('Deleting: ', instance.uploaded_file)
        if os.path.exists(instance.uploaded_file.path):
            os.unlink(instance.uploaded_file.path)

post_delete.connect(delete_filefield, sender=FileUploadHistory)