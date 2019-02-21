from django.shortcuts import render_to_response
from django.template.context import RequestContext
from rest_framework import status
from rest_framework.generics import CreateAPIView, RetrieveAPIView, GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from neo_importer.models import FileUploadHistory
from neo_importer.serializers import NeoFileImporterSerializer, FileUploadHistorySerializer
from neo_importer.utils import format_results


def importers_index(request, importer_site):

    return render_to_response('neo_importer/importers_in    dex.html', {'importer_site': importer_site}, RequestContext(request))


class UploadFileApiView(CreateAPIView):
    serializer_class = NeoFileImporterSerializer
    queryset = FileUploadHistory.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        file_upload_history = self.perform_create(serializer)

        initial_data = serializer.validated_data
        initial_data['uploaded_file'] = file_upload_history.uploaded_file.url
        initial_data['id'] = file_upload_history.id
        serializer = self.get_serializer_class()(initial=initial_data)
        headers = self.get_success_headers(serializer.data)
        return Response(initial_data, status=status.HTTP_201_CREATED, headers=headers)

    def check_permissions(self, request):
        super(UploadFileApiView, self).check_permissions(request)
        importer = self.kwargs.get('importer')
        user = request.user
        if not user.has_perms(importer.get_permissions()):
            self.permission_denied(
                request, message='Permission Denied'
            )

    def get_serializer_class(self):
        serializer_class = self.kwargs.get('importer').get_serializer_class()

        if serializer_class:
            return serializer_class

        else:
            return super(UploadFileApiView, self).get_serializer_class()

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        kwargs['user'] = self.request.user
        kwargs['process_importer'] = False
        kwargs['importer'] = self.kwargs.get('importer')

        return serializer_class(*args, **kwargs)

    def perform_create(self, serializer):

        file_upload_history = serializer.save()
        file_upload_history.type = self.kwargs.get('importer').get_importer_type()
        file_upload_history.user = self.request.user
        file_upload_history.set_form_params(self.request.POST)
        file_upload_history.save()

        return file_upload_history


class DetailFileHistoryApiView(RetrieveAPIView):
    serializer_class = FileUploadHistorySerializer
    queryset = FileUploadHistory.objects.all()

    def check_permissions(self, request):
        super(DetailFileHistoryApiView, self).check_permissions(request)
        importer = self.kwargs.get('importer')
        user = request.user
        if not user.has_perms(importer.get_permissions()):
            self.permission_denied(
                request, message='Permission Denied'
            )


class ValidateFileHistoryApiView(GenericAPIView,):
    serializer_class = NeoFileImporterSerializer
    queryset = FileUploadHistory.objects.all()

    def check_permissions(self, request):
        super(ValidateFileHistoryApiView, self).check_permissions(request)
        importer = self.kwargs.get('importer')
        user = request.user
        if not user.has_perms(importer.get_permissions()):
            self.permission_denied(
                request, message='Permission Denied'
            )

    def get_queryset(self):
        return super(ValidateFileHistoryApiView, self).get_queryset().filter(
            type=self.kwargs.get('importer').get_importer_type()
        )

    def get_serializer_class(self):
        serializer_class = self.kwargs.get('importer').get_serializer_class()

        if serializer_class:
            return serializer_class

        else:
            return super(ValidateFileHistoryApiView, self).get_serializer_class()

    def get(self, request, *args, **kwargs):
        file_upload_history = self.get_object()

        importer = kwargs.get('importer')

        ctx = {}

        valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        data = file_upload_history.get_form_params()

        serializer = self.get_serializer_class()(valid_extensions, self.request.user, data=data, no_validate_file=True)
        serializer.is_valid()

        importer.execute_importer(
            file_upload_history,
            extra_user_params=serializer.validated_data,
        )

        results = importer.get_results(file_upload_history)

        ctx['results'] = format_results(results)
        ctx['celery_tasks'] = getattr(importer, 'celery_tasks', None)

        ctx['upload_file_url'] = importer.get_api_upload_file_url()
        ctx['process_file_url'] = importer.get_api_process_file_url(file_upload_history.id)

        return Response(ctx)


class ProcessFileHistoryApiView(GenericAPIView,):
    serializer_class = NeoFileImporterSerializer
    queryset = FileUploadHistory.objects.all()

    def check_permissions(self, request):
        super(ProcessFileHistoryApiView, self).check_permissions(request)
        importer = self.kwargs.get('importer')
        user = request.user
        if not user.has_perms(importer.get_permissions()):
            self.permission_denied(
                request, message='Permission Denied'
            )

    def get_queryset(self):
        return super(ProcessFileHistoryApiView, self).get_queryset().filter(
            type=self.kwargs.get('importer').get_importer_type()
        )

    def get_serializer_class(self):
        serializer_class = self.kwargs.get('importer').get_serializer_class()

        if serializer_class:
            return serializer_class

        else:
            return super(ProcessFileHistoryApiView, self).get_serializer_class()

    def post(self, request, *args, **kwargs):
        file_upload_history = self.get_object()

        importer = kwargs.get('importer')

        ctx = {}

        valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        data = file_upload_history.get_form_params()

        serializer = self.get_serializer_class()(valid_extensions, self.request.user, data=data, no_validate_file=True)
        serializer.is_valid()

        importer.execute_importer(
            file_upload_history,
            extra_user_params=serializer.validated_data,
        )

        results = importer.get_results(file_upload_history)
        ctx['results'] = format_results(results)
        ctx['celery_tasks'] = getattr(importer, 'celery_tasks', None)
        return Response(ctx)


class ResultsFileHistoryApiView(GenericAPIView,):
    serializer_class = NeoFileImporterSerializer
    queryset = FileUploadHistory.objects.all()

    def check_permissions(self, request):
        super(ResultsFileHistoryApiView, self).check_permissions(request)
        importer = self.kwargs.get('importer')
        user = request.user
        if not user.has_perms(importer.get_permissions()):
            self.permission_denied(
                request, message='Permission Denied'
            )

    def get_queryset(self):
        return super(ResultsFileHistoryApiView, self).get_queryset().filter(
            type=self.kwargs.get('importer').get_importer_type()
        )

    def get_serializer_class(self):
        serializer_class = self.kwargs.get('importer').get_serializer_class()

        if serializer_class:
            return serializer_class

        else:
            return super(ResultsFileHistoryApiView, self).get_serializer_class()

    def get(self, request, *args, **kwargs):
        file_upload_history = self.get_object()

        importer = kwargs.get('importer')

        ctx = {}

        valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        data = file_upload_history.get_form_params()

        serializer = self.get_serializer_class()(valid_extensions, self.request.user, data=data, no_validate_file=True)
        serializer.is_valid()


        results = importer.get_results(file_upload_history)
        importer.file_upload_history = file_upload_history

        ctx['results'] = format_results(results)
        ctx['celery_tasks'] = getattr(importer, 'celery_tasks', None)

        # ctx['upload_file_url'] = importer.get_api_upload_file_url()
        # ctx['process_file_url'] = importer.get_process_file_url(file_upload_history.id)

        return Response(ctx)


class ImporterInformationApiView(APIView):

    def check_permissions(self, request):
        super(ImporterInformationApiView, self).check_permissions(request)
        importer = self.kwargs.get('importer')
        user = request.user
        if not user.has_perms(importer.get_permissions()):
            self.permission_denied(
                request, message='Permission Denied'
            )

    def get(self, request, *args, **kwargs):

        importer = kwargs.get('importer')

        ctx = {}

        ctx['valid_extensions'] = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        # template_file = kwargs.get('template_file', importer.get_importer_link())
        # kwargs['template_file'] = template_file
        ctx['importer_type'] = importer.get_importer_type()
        ctx['entity_name'] = importer.entity_name
        ctx['importer_title'] = importer.get_importer_title()
        ctx['title'] = importer.get_importer_title()
        if importer.get_html_helper_messages():
            ctx['html_messages'] = importer.get_html_helper_messages()

        ctx['template_file_url'] = importer.get_api_template_file_url()
        ctx['upload_file_url'] = importer.get_api_upload_file_url()
        ctx['validate_file_url'] = importer.get_api_validate_file_url('__pk__')
        ctx['results_file_url'] = importer.get_api_results_file_url('__pk__')
        ctx['process_file_url'] = importer.get_api_process_file_url('__pk__')
        ctx['detail_file_url'] = importer.get_api_detail_file_url('__pk__')
        ctx['form_api'] = importer.get_form_api()
        ctx['celery_tasks'] = getattr(importer, 'celery_tasks', None)
        return Response(ctx)
