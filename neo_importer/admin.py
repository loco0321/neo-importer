from django.contrib import admin

from neo_importer.models import FileUploadHistory


class FileUploadHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'upload_timestamp', 'start_execution_timestamp', 'finish_execution_timestamp',
                    'duration', 'state', )
    list_filter = ('type', 'state', 'upload_timestamp')
    search_fields = ('user__username', 'upload_timestamp', 'id')
    raw_id_fields = ('user',)
    readonly_fields = ('uploaded_file', 'results', )


admin.site.register(FileUploadHistory, FileUploadHistoryAdmin)
