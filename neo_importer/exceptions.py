# -*- coding: utf-8 -*-
import traceback

from django.core.exceptions import ValidationError


class DataImporterError(ValidationError):
    """
    Base class for all data importer exceptions."
    Attention: Use unicode messages instead of strings: u'...' instead of '...' to avoid UnicodeDecodeErrors
    """
    pass


class SkipRow(DataImporterError):
    "This exception must be used when the line is recognized and must be ignored."
    pass


class InvalidLength(DataImporterError):
    "This is a internal exception."
    pass


class ImporterWarning(DataImporterError):
    "This exception must be used when the line has incorrect values and it can not be processed."
    pass


class ImporterError(DataImporterError):
    "This exception must be used when the line has incorrect values and it can not be processed."
    pass


class FileAlreadyProcessed(DataImporterError):
    "Is is trying to process a already processed file."
    pass


class StopImporter(DataImporterError):
    """
    This exception must be used when the file or a line has a critical error and the importation must be stopped.

    File Importer Error try to return a user friendly message but collect a lot of information for log or debug purposes too.
    * message - user end message to detail error
    * value - the value that raised the Exception.
    * field - The field or column name of the error
    * line_number - The line in file that caused the error
    * original_traceback - Catch original exception traceback
    * original_exception- Can be used to automatically extract traceback and message
    * use_original_message: Use exception_message in __str__ instead of try to guess row, column, etc.
    """

    def __init__(self, message='', value='', column_number='', column_name='', \
                 original_traceback='', row='', line_number='', original_exception=None,
                 use_original_message=False):
        self.column_number = column_number
        self.column_name = column_name
        self.line_number = line_number
        self.original_traceback = original_traceback
        self.row = row
        self.value = value
        self.original_exception = original_exception
        if self.original_exception:
            self.original_traceback = repr(traceback.format_exc())
            self.exception_message = unicode(self.exception_message) or unicode(self.original_exception)
        self.exception_message = message
        self.use_original_message = use_original_message

    def detailed_user_message(self):
        if self.use_original_message:
            msg = u''
            if self.line_number:
                msg += u"line %s:" % self.line_number

            msg += self.exception_message
            return msg

        column_msg = u''
        if self.column_name:
            column_msg += u'column "%s" ' % self.column_name
        if self.column_number:
            column_msg += u'position %s ' % self.column_number
        if self.value:
            column_msg += u'value %s ' % self.value

        line_msg = u''
        if self.line_number:
            line_msg += u" line %s " % self.line_number

        msg = u''
        if column_msg or line_msg:
            msg = u"Error on %s %s: %s" % (column_msg, line_msg, self.exception_message)
        elif self.exception_message:
            msg = self.exception_message
        return msg

    def __str__(self):
        return self.detailed_user_message()

    def __unicode__(self):
        return self.detailed_user_message()
