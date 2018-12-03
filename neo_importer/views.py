from django.shortcuts import render_to_response
from django.template.context import RequestContext
from rest_framework.generics import CreateAPIView, RetrieveAPIView, GenericAPIView
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.views import APIView

from neo_importer.models import FileUploadHistory
from neo_importer.serializers import NeoFileImporterSerializer, FileUploadHistorySerializer


def importers_index(request, importer_site):

    return render_to_response('neo_importer/importers_in    dex.html', {'importer_site': importer_site}, RequestContext(request))


class UploadFileApiView(CreateAPIView):
    serializer_class = NeoFileImporterSerializer
    queryset = FileUploadHistory.objects.all()

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

        # form_class = importer.get_form()
        # formset_class = importer.get_formset_class()

        valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        data = file_upload_history.get_form_params()
        # form = form_class(valid_extensions, request.user, data=data, no_validate_file=True)
        # form.is_valid()

        # formset_cleaned_data = None
        # formset = None
        # if formset_class:
        #     formset = formset_class(data=data)
        #     formset.is_valid()
        #     formset_cleaned_data = formset.cleaned_data
        serializer = self.get_serializer_class()(valid_extensions, self.request.user, data=data, no_validate_file=True)
        serializer.is_valid()

        importer.execute(
            file_upload_history,
            extra_user_params=serializer.validated_data,
            # formset_params=formset_cleaned_data
        )

        results = importer.get_results(file_upload_history)
        # template = importer.get_show_validations_template()
        ctx['results'] = {
            'columns_mapping': results.columns_mapping,
            'columns_to_group': results.columns_to_group,
            'data': results.data,
            'grouped_fields': results.grouped_fields,
            'grouped_fields_labels': results.grouped_fields_labels,
            'ignored_elements': results.ignored_elements,
            'single_elements': results.single_elements,

        }

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

        # form_class = importer.get_form()
        # formset_class = importer.get_formset_class()

        valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        data = file_upload_history.get_form_params()
        # form = form_class(valid_extensions, request.user, data=data, no_validate_file=True)
        # form.is_valid()

        # formset_cleaned_data = None
        # formset = None
        # if formset_class:
        #     formset = formset_class(data=data)
        #     formset.is_valid()
        #     formset_cleaned_data = formset.cleaned_data
        serializer = self.get_serializer_class()(valid_extensions, self.request.user, data=data, no_validate_file=True)
        serializer.is_valid()

        importer.execute(
            file_upload_history,
            extra_user_params=serializer.validated_data,
            # formset_params=formset_cleaned_data
        )

        results = importer.get_results(file_upload_history)
        # template = importer.get_show_validations_template()
        ctx['results'] = {
            'columns_mapping': results.columns_mapping,
            'columns_to_group': results.columns_to_group,
            'data': results.data,
            'grouped_fields': results.grouped_fields,
            'grouped_fields_labels': results.grouped_fields_labels,
            'ignored_elements': results.ignored_elements,
            'single_elements': results.single_elements,

        }

        # ctx['upload_file_url'] = importer.get_api_upload_file_url()
        # ctx['process_file_url'] = importer.get_process_file_url(file_upload_history.id)

        return Response(ctx)

    # def get(self, request, *args, **kwargs):
    #     return Response({})

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

        # form_class = importer.get_form()
        # formset_class = importer.get_formset_class()

        valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        data = file_upload_history.get_form_params()

        serializer = self.get_serializer_class()(valid_extensions, self.request.user, data=data, no_validate_file=True)
        serializer.is_valid()


        results = importer.get_results(file_upload_history)
        importer.file_upload_history = file_upload_history

        ctx['results'] = {
            'columns_mapping': results.columns_mapping,
            'columns_to_group': results.columns_to_group,
            'data': results.data,
            'grouped_fields': results.grouped_fields,
            'grouped_fields_labels': results.grouped_fields_labels,
            'ignored_elements': results.ignored_elements,
            'single_elements': results.single_elements,

        }

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

        form_class = importer.get_form()
        formset_class = importer.get_formset_class()

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

        return Response(ctx)
