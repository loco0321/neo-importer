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
            self.data = FileUploadHistory().decode_data(encoded_data)
        return self.data

    # def load_from_jobs(self, file_upload_history, transaction=None):
    #     result = []
    #     total_waiting = 0
    #     total_created = 0
    #     total_rejected = 0
    #     if transaction:
    #         jobs = get_jobs_by_transaction(file_upload_history, transaction)
    #     else:
    #         jobs = file_upload_history.job_set.all()
    #
    #     for job in jobs:
    #         input = job.input()
    #
    #         if job.state == job.CREATED:
    #             total_created += 1
    #         elif job.state in (job.REJECTED, job.REJECTED_QUEUED):
    #             total_rejected += 1
    #         else:
    #             total_waiting += 1
    #
    #         if validate_ip(job.agent_name) and job.flowbot_job_id and job.state == job.REJECTED:
    #             screenshot_url = 'http://{0}:8080/screenshot/{1}'.format(
    #                 job.agent_name,
    #                 job.flowbot_job_id
    #             )
    #
    #         else:
    #             screenshot_url = None
    #
    #         result.append({
    #             'id': job.id,
    #             'state': job.state,
    #             'input': input,
    #             'output': job.cleaned_output(),
    #             'extra_params': job.extra(),
    #             'screenshot': screenshot_url
    #         })
    #
    #     if len(jobs) > 0:
    #         progress = round((total_created+total_rejected)*100/len(jobs),1)
    #
    #     else:
    #         progress = 0
    #     self.data_jobs = {'jobs': result,
    #                       'total': len(jobs),
    #                       'progress': progress,
    #                       'total_waiting': total_waiting,
    #                       'total_created': total_created,
    #                       'total_rejected': total_rejected}

    # def load_from_all_jobs(self, file_upload_history, transaction=None):
    #     result = []
    #     total_waiting = 0
    #     total_created = 0
    #     total_rejected = 0
    #     jobs = file_upload_history.job_set.all()
    #
    #     for job in jobs:
    #         input = job.input()
    #
    #         if job.state == job.CREATED:
    #             total_created += 1
    #         elif job.state in (job.REJECTED, job.REJECTED_QUEUED):
    #             total_rejected += 1
    #         else:
    #             total_waiting += 1
    #
    #         result.append({
    #             'id': job.id,
    #             'state': job.state,
    #             'input': input,
    #             'output': job.cleaned_output()
    #         })
    #
    #     if len(jobs) > 0:
    #         progress = round((total_created + total_rejected) * 100 / len(jobs), 1)
    #
    #     else:
    #         progress = 0
    #     self.data_all_jobs = {'jobs': result,
    #                           'total': len(jobs),
    #                           'progress': progress,
    #                           'total_waiting': total_waiting,
    #                           'total_created': total_created,
    #                           'total_rejected': total_rejected}


    # def get_single_elements(self):
    #     l = list(self.elements)
    #     for key in self.list_elements + self.ignored_elements:
    #         try:
    #             l.remove(key)
    #         except ValueError:
    #             continue
    #     return l

    def prepare_list_elements(self, group):
        grouped_data = []
        for field_mapping in self.grouped_fields.values():
             grouped_data.append([{'field': field_mapping, 'value': x} for x in group.get(field_mapping, '')])

        return zip(*grouped_data)