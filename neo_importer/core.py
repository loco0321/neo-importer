# coding=utf-8
import json
import re
import time
import traceback
from collections import OrderedDict

from datetime import date, datetime

import unicodedata

import sys
from functools import update_wrapper

import six
import xlwt
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render_to_response, render
from django.template.context import RequestContext
from django.template.defaultfilters import slugify
from django.urls import reverse

from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from xlrd import open_workbook

from neo_importer.exceptions import ImporterError, InvalidLength, SkipRow, ImporterWarning, StopImporter, \
    FileAlreadyProcessed
from neo_importer.forms import NeoFileImporterForm
from neo_importer.helper import NeoResultHelper
from neo_importer.models import FileUploadHistory
from neo_importer.readers import ExcelReaderAllAsString, ExcelReaderInMemoryAllAsString
from neo_importer.serializers import NeoFileImporterSerializer
from neo_importer.sheets import SheetData, ExcelData
from neo_importer.validators import RequiredValidator
from neo_importer.views import UploadFileApiView, ImporterInformationApiView, DetailFileHistoryApiView, \
    ValidateFileHistoryApiView, ProcessFileHistoryApiView, ResultsFileHistoryApiView


class NeoImporterReport(object):
    def __init__(self):
        self.amount_of_lines = 0
        self.errors = []
        self.infos = []
        self.warnings = []

    def line_read(self):
        self.amount_of_lines += 1

    def has_error(self):
        return len(self.errors) > 0

    def format_msg(self, msg):
        return msg

    def add_warning(self, msg):
        self.warnings.append(self.format_msg(msg))

    def add_info(self, msg):
        self.infos.append(self.format_msg(msg))

    def add_error(self, msg):
        self.errors.append(self.format_msg(msg))

    def to_encoded_json(self):
        import zlib, base64
        j = json.dumps(self, default=lambda o: o.__dict__)
        try:
            return base64.b64encode(zlib.compress(bytearray(j, encoding='UTF-8'), 9)).decode('utf-8')
        except:
            return base64.b64encode(zlib.compress(j,9)).decode('utf-8')

    def create_excel_report(self, fileuploadhistory, importer):
        from xlutils.copy import copy
        if re.findall('.xls', fileuploadhistory.original_filename):
            rb = open_workbook(
                fileuploadhistory.uploaded_file.path,
                #on_demand=True,
                # formatting_info=True
            )

            workbook = copy(rb)
            errors = fileuploadhistory.decode_results()

            worksheet = workbook.get_sheet(0)
            # last_used_col = worksheet.last_used_col + 1
            # write column errors

            style_titles = xlwt.Style.easyxf('font: bold on; align: vert center, horiz center;')
            style_first_column = xlwt.Style.easyxf('font: bold on; align: vert center, horiz center; border: left dotted;')

            first_column = None
            last_column = None
            for key, column in importer.columns.items():

                if first_column is None:
                    first_column = column
                elif column <= first_column:
                    first_column = column

                if last_column is None:
                    last_column = column
                elif column >= last_column:
                    last_column = column

            last_used_col = last_column + 1

            for key, column in importer.columns.items():
                if column == first_column:
                    style = style_first_column
                else:
                    style = style_titles

                worksheet.row(0).write(last_used_col + column, key, style)

            worksheet.row(0).write(last_used_col * 2, 'Line Errors', style_titles)
            worksheet.row(0).write(last_used_col * 2 + 1, 'Group Errors', style_titles)
            for error in errors.get('errors', []):
                group_errors = []
                for line_error in error.get('msg'):
                    if line_error.get('field'):
                        line_number = line_error.get('line') - 1
                        worksheet.row(line_number).write(
                            last_used_col + importer.columns.get(line_error.get('field')),
                            u'{0}. Value: {1}'.format(
                                line_error.get('msg', 'No message'),
                                line_error.get('value', '')
                            )
                        )
                    elif line_error.get('line'):
                        line_number = line_error.get('line') - 1
                        group_errors_col = last_used_col * 2
                        worksheet.row(line_number).write(
                            group_errors_col,
                            line_error.get('msg', 'No message'),
                        )

                    else:
                        group_errors.append(line_error.get('msg'))

                    group_errors_col = last_used_col*2
                    group_errors_col += 1
                    if group_errors:
                        worksheet.write_merge(error.get('first_line')-1, error.get('last_line')-1, group_errors_col, group_errors_col, u' \n'.join(group_errors))

                    # dict_errors = {}
                # for line_error in error.get('msg'):
                #     line_number = line_error.get('line') - 1
                #
                #     if not dict_errors.has_key(line_number):
                #         dict_errors[line_number] = []
                #
                #     dict_errors[line_number].append(
                #         u'Line {0} "{1}": {2}. Value: {3}'.format(
                #             line_error.get('line'),
                #             line_error.get('field'),
                #             line_error.get('msg', 'No message'),
                #             line_error.get('value', '')
                #         )
                #     )
                #
                # worksheet = workbook.get_sheet(0)
                # last_used_col = worksheet.last_used_col + 1
                # worksheet.row(0).write(last_used_col, 'Field Errors')
                # for line, error_list in dict_errors.items():
                #     row = worksheet.row(line)
                #     row.write(
                #         last_used_col,
                #         u' | '.join(error_list)
                #     )
            return workbook

    def as_abbreviated_text(self):
        if six.PY2:
            return smart_unicode(self, 'utf-8')[0:1000]

        else:
            return str(self)[0:1000]


class NeoImporter(object):
    """
    Generic Data Importer
    * @valid_lengths: define only if you need to restrict line lenght
    * @'valid_row_lengths: An integer or a list of allowed row lengths
    * @columns:
    * @column_quantity: The required amount of columns. If it´s 0 validation isn ´t done.
    * @first_valid_line: first line of data (do not consider header)
    * @auto_assign_columns: if True, the file will use the first line of the file to fill self.columns attribute
    * @valid_parameters: if auto_assign_columns is True, only these attributes will be used to fill self.columns attribute
    * @validate_column_names: if True the importer will read the first line content and validate with the template columns order
    """
     # False to avoid validating columns on non specified importers

    def __init__(self, reader, first_valid_line=0, auto_assign_columns=False, column_quantity=0, validate_column_names=False, **kwargs):
        self.validate_column_names = validate_column_names
        self.reader = reader
        self.first_valid_line = first_valid_line
        self.auto_assign_columns = auto_assign_columns
        self.valid_parameters = [] # used to validate columns if auto_assign_columns is True
        self.valid_row_lengths = None
        self.report = NeoImporterReport()
        self.columns = {}
        self.validators = {}
        self.user = kwargs.get('user', None)
        self.extra_user_params = {}
        self.column_quantity = column_quantity
        self.user_line_number = 1
        self.show_messages = True
        # It store all the cleaned data to be used later
        self.all_cleaned_data = []
        self.extra_messages = []


    def _auto_assign_columns(self, data_source):
        "Columns are auto-defined by the first line of the file"
        params = self.reader.lines(data_source).next()[1] # reading first line
        self.columns = dict((value, index) for index, value in enumerate(params))
        tmp_columns = dict((value, index) for index, value in enumerate(params)) # used just to iterate the parameters
        if self.valid_parameters:
            for parameter in tmp_columns.keys():
                if parameter not in self.valid_parameters:
                    self.columns.pop(parameter)

    def remove_accentuation(self, string):
        if isinstance(string, unicode):
            return unicodedata.normalize("NFKD", string).encode('ascii', 'ignore')
        return unicodedata.normalize("NFKD", string.decode('utf-8')).encode('ascii', 'ignore')

    def to_int(self, value, blank_must_be_converted_to_zero=False):
        if value:
            return int(value)
        if blank_must_be_converted_to_zero:
            return 0
        else:
            int(value) # this will raise an exception

    def float_to_decimal(self, value):
        return Decimal(str(value))

    def to_decimal(self, string):
        """ Converts a '"123.456,78"' string into a Decimal """
        return Decimal(string.replace('"', '').replace('.', '').replace(',', '.'))

    def to_date(self, string, date_format):
        """
        Converts a string into a date type
         * string: string date value
         * date_format: string date format
        """
        return date(*time.strptime(string, date_format)[:3])

    def validate_row_length(self, row):
        """
        Validates the row before trying to parse it, subclasses should add additional validation
        Validate only applies when self.valid_row_lengths is defined.
        """
        if not self.valid_row_lengths:
            return
        valid_row_lengths = self.valid_row_lengths
        if isinstance(self.valid_row_lengths, int):
            valid_row_lengths = [self.valid_row_lengths, ]

        if len(row) not in valid_row_lengths:
            raise InvalidLength

    def pre_clean(self, data):
        """A hook to custom row cleans."""
        return data

    def post_clean(self, cleaned_data):
        "A hook to custom row cleans. 'data' is a dictionary that contains the pertinent information of a row."
        return cleaned_data

    def add_error(self, msg, row=None):
        if row:
            self.report.add_error({'msg': msg,
                                   'row': dict(zip(self.columns, row))})
        else:
            self.report.add_error({'msg': msg})

    def strip_value(self, s):
        if isinstance(s, str):
            new = []
            for i in s:
                o = ord(i)
                if (o >= 32 and o <= 126):
                    new.append(i)
            new = ''.join(new)
            return new.strip(" ")
        else:
            return s

    def validate_fields(self, row):
        cleaned = {}
        errors = []
        for key, value in row.items():
            value = self.strip_value(value)
            if key in self.validators:
                key_validators = self.validators[key]
                if isinstance(key_validators, (list, tuple)):
                    for validator in key_validators:
                        try:
                            validator(value)
                        except (ImporterError, ValidationError) as e:
                            errors.append({'field': key, 'error': ' - '.join(e.messages), 'value': value})
                else:
                    try:
                        key_validators(value)
                    except (ImporterError, ValidationError) as e:
                        errors.append({'field': key, 'error': ' - '.join(e.messages), 'value': value})

            validators = list()
            validators.append('clean_' + key.replace(' ', '_'))
            validators.append('clean_' + slugify(key).replace('-','_'))

            validators = set(validators)
            for validator in validators:
                if hasattr(self, validator):
                    try:
                        cleaned[key] = getattr(self, validator)(value)
                        break
                    except (ImporterError, ValidationError) as e:
                        errors.append({'field': key, 'error': ' - '.join(e.messages), 'value': value})
                else:
                    cleaned[key] = value

        if errors:
            return {'cleaned': False, 'data': errors, 'cleaned_data': cleaned}

        return {'cleaned': True, 'data': cleaned}

    def clean(self, row):
        """
        Clean all the fields in the 'row' dictionary by calling a 'validate_key' method,
        where 'key' is the 'key' from dictionary. The validate method must the defined
        in the class that inherit this one.
        """
        row = self.pre_clean(row)
        if row is None:
            raise ImporterError('The pre_clean must return a valid row!')
        try:
            self.validate_row_length(row)
        except InvalidLength:
            self.add_error(u'Line: %s: Invalid row length found (%s) valid is %s' %
                            (self.user_line_number, len(row), str(self.valid_row_lengths)), row)
            return

        if not isinstance(row, dict):
            mapped_row = self.to_dictionary(row)
        else:
            mapped_row = row

        result = self.validate_fields(mapped_row)

        if result.get('cleaned'):
            result['data'] = self.post_clean(result.get('data'))
        if result.get('data') is None:
            raise Exception('The post_clean must return a valid row!') # this is a programming error
        return result

    def to_dictionary(self, row):
        "Convert a list into a dictionary, using the 'columns' as the map"
        output = OrderedDict()
        for key, value in self.columns.items():
            try:
                value = self.strip_value(row[value])
            except IndexError:
                value = None
            output[key] = value
        return output

    def process_row(self, row):
        try:
            cleaned_data = self.clean(row)
            self.save(cleaned_data)
            return cleaned_data
        except SkipRow:
            return
        except (ValidationError, ImporterWarning) as e:
            if hasattr(e, 'messages') and e.messages:
                for error in e.messages:
                    try:
                        self.add_error(u'Line %s: %s' % (self.user_line_number, error), row)
                    except UnicodeDecodeError:
                        self.add_error(u'[line:%s] This line was not imported because some characters \
                                                  could not be interpreted.' % self.user_line_number)
            else:
                try:
                    self.add_error(u'Line %s: %s' % (self.user_line_number, e), row)
                except UnicodeDecodeError:
                    self.add_error(u'Line %s: This line was not imported because some characters \
                                              could not be interpreted.' % self.user_line_number)

    def save(self, cleaned_data):
        "Receive a dictionary 'data' that contains the pertinent information of a row. Must save data properly."
        self.all_cleaned_data.append(cleaned_data)

    def pre_execute(self, data_source=None):
        "Hook to custom tasks before execution"
        pass

    def post_execute(self, data_source=None):
        "Hook to custom tasks after execution"
        pass

    def validate_column_quantity(self, row):
        """If applicable, check if expected column quantity is equal to existent quantity.
        """
        if self.column_quantity:
            clear_row = [i for i in row if i]
            if self.column_quantity != len(clear_row):
                raise ImporterError('Invalid column quantity. Expected:%s - Existent:%s' % (self.column_quantity, len(row)), use_original_message=True)

    def validate_with_template(self, row):
        """
        Check if the headers of the imported file is the same as the template file of the importer.
        """
        for column, index in self.columns.items():
            if row[index] == column:
                continue
            else:
                raise StopImporter("You have uploaded a wrong or outdated template. <a class='need_help_template'>Need some help?</a>")

    def execute_internal(self, data_source):
        self.pre_execute(data_source)
        if self.auto_assign_columns:
            self._auto_assign_columns(data_source)

        for line_number, row in self.reader.lines(data_source):
            self.user_line_number = line_number + 1  # For displaying user messages, line starts in 1
            try:
                if line_number == 0:
                    self.validate_column_quantity(row)
                    if self.validate_column_names:
                        self.validate_with_template(row)
                if line_number < self.first_valid_line:
                    continue
                self.process_row(row)
            except ImporterError as e:
                e.exception_message = e.detailed_user_message()
                e.original_traceback = repr(traceback.format_exc())
                e.line_number = self.user_line_number
                e.row = row
                raise (e, None, sys.exc_info()[2])
            self.report.line_read()

        self.post_execute(data_source)

    def save_historic(self, file_upload_history, report):
        # if the string is too long we will get the error:
        # "pyodbc.Error: HY000 - The driver did not supply an error"
        # to avoid this we limited the results size
        file_upload_history.results = report.to_encoded_json() # must be unicode, not str
        file_upload_history.state = FileUploadHistory.PROCESSED
        file_upload_history.finish_execution_timestamp = datetime.now()
        file_upload_history.save(force_update=True)

    def post_save_historic(self, file_upload_history):
        "Hook to custom tasks after save the historic: FileUploadHistory model."
        pass

    #@transaction.commit_manually
    def execute(self, file_upload_history, extra_user_params={}):
        """ This is the entry method for DataImporter class to import a file. """
        if file_upload_history.is_processed():
            raise FileAlreadyProcessed('This file has already been executed.')
        file_upload_history.state = FileUploadHistory.PROCESSING
        file_upload_history.start_execution_timestamp = datetime.now()
        # Lock the object in the transaction!?
        # Using force_update to try to avoid pyodbc bugs.
        # Using force_update may result in "transaction pending" errors.
        file_upload_history.save(force_update=True)
        transaction.commit()

        self.user = file_upload_history.user
        self.extra_user_params = extra_user_params

        try:
            data_source = file_upload_history.uploaded_file.path
            self.execute_internal(data_source)
            self.save_historic(file_upload_history, self.report)
            self.post_save_historic(file_upload_history)
        except ImporterError as e:
            transaction.rollback()
            file_upload_history.results = e.detailed_user_message()
            file_upload_history.state = FileUploadHistory.FAILED
            file_upload_history.finish_execution_timestamp = datetime.now()
            file_upload_history.save(force_update=True)
            transaction.commit()
            self.report.add_error(e.detailed_user_message() + repr(traceback.format_exc()))
            raise Exception(e, None, sys.exc_info()[2])
        # except Exception as e:
        #     transaction.rollback()
        #     file_upload_history.results = str(e)
        #     file_upload_history.state = FileUploadHistory.FAILED
        #     file_upload_history.finish_execution_timestamp = datetime.now()
        #     file_upload_history.save(force_update=True)
        #     transaction.commit()
        #     self.report.add_error(str(e) + repr(traceback.format_exc()))
        #     raise Exception(e, None, sys.exc_info()[2])
        else:
            transaction.commit()
            return self.report


class GroupNeoImporter(NeoImporter):
    def __init__(self, reader, first_valid_line=0, auto_assign_columns=False,
                 indexes_of_key_columns_to_group=[], dependent_errors=True, *args, **kwargs):
        super(GroupNeoImporter, self).__init__(reader, first_valid_line=first_valid_line, auto_assign_columns=auto_assign_columns, **kwargs)

        self.indexes_of_key_columns_to_group = indexes_of_key_columns_to_group # indexes of columns that will be used to group rows
        self.dependent_errors = dependent_errors

        self._grouped_rows = []
        self._grouped_row_messages = []
        self._last_group = []
        self._current_group = []
        self._first_line_of_group = 0
        self._last_line_of_group = 0
        self._current_group_has_errors = False
        self.grouped_fields = []
        self.rows = []
        self._group_cleaned_data = []

    def add_error(self, msg, group=None):
        if group:
            if all(isinstance(item, dict) for item in group):
                # It means row is a group of rows
                data = self.get_info_grouped(group=group, character_for_join=None)
                self.report.add_error({'msg': msg,
                                       'group': data,
                                       'first_line': self._first_line_of_group,
                                       'last_line': self._last_line_of_group-1})
            else:
                super(GroupNeoImporter, self).add_error(msg, group)

    def execute_internal(self, data_source):
        self.pre_execute(data_source)

        if self.auto_assign_columns:
            self._auto_assign_columns(data_source)

        for line_number, row in self.reader.lines(data_source):
            self.user_line_number = line_number + 1  # For displaying user messages, line starts in 1

            if line_number == 0 and self.validate_column_names:
                self.validate_with_template(row)

            if line_number < self.first_valid_line:
                continue

            self.rows.append(row)
            try:
                self._current_group = self.get_current_group(row)
                # we ignore first line, but it need to take care files with only one line
                if not self._last_group:
                    self._last_group = self._current_group
                    self._first_line_of_group = self.user_line_number
                    self._last_line_of_group = self.user_line_number
                self.process_row(row)
            except ImporterError as e:
                e.exception_message = e.detailed_user_message()
                e.original_traceback = repr(traceback.format_exc())
                e.line_number = self.user_line_number
                e.row = row
                raise (e, None, sys.exc_info()[2])
            self.report.line_read()

        try:
            self.user_line_number += 1
            self.process_last_set_of_rows()
        except ImporterError as e:
            e.exception_message = e.detailed_user_message()
            e.original_traceback = repr(traceback.format_exc())
            e.line_number = self.user_line_number
            e.row = row
            raise (e, None, sys.exc_info()[2])

        self.post_execute(data_source)

    def get_current_group(self, row):
        "It iterates all key columns and create a list with its values"
        current_group = []
        for column in self.indexes_of_key_columns_to_group:
            current_group.append(row[column])
        return current_group

    def group_clean(self, grouped_cleaned_data, grouped_rows=None):
        return grouped_cleaned_data

    def process_last_set_of_rows(self):
        try:
                                                        #Only has rows cleaned,  #has all rows
            self._group_cleaned_data = self.group_clean(self._group_cleaned_data, self._grouped_rows)
        except (ValidationError, ImporterWarning) as e:
            for msg in e.messages:
                self._grouped_row_messages.append({'msg': msg})
            self.add_error(self._grouped_row_messages, self._grouped_rows)
        else:
            if self.dependent_errors and self._current_group_has_errors:
                self.add_error(self._grouped_row_messages, self._grouped_rows)
            else:
                try:
                    if self._group_cleaned_data:
                        self.save(self._group_cleaned_data) # process last group of rows

                except SkipRow:
                    return
                except (ValidationError, ImporterWarning) as e:
                    try:
                        if hasattr(e, 'messages'):
                            message = e.messages[0]
                        else:
                            if six.PY2:
                                message = unicode(e)
                            else:
                                message = str(e)

                        self.add_error(u'Line %s: %s' % (self.user_line_number - 1, message), self._grouped_rows)
                    except UnicodeDecodeError:
                        self.add_error(u'Line %s: This line was not imported because some characters could not be interpreted.' % (self.user_line_number - 1,))
        finally:
            self._grouped_rows = [] # it starts a new group of rows
            self._grouped_row_messages = []
            self._group_cleaned_data = []
            self._last_group = self._current_group
            self._current_group_has_errors = False
            self._first_line_of_group = self.user_line_number
            self._last_line_of_group = self.user_line_number

    def process_row(self, row):
        if self._last_group != self._current_group:
            self.process_last_set_of_rows() # grouped rows of cleaned_data
        try:
            result = self.clean(row)

        except SkipRow:
            return

        except (ValidationError, ImporterWarning) as e:
            for msg in e.messages:
                self._grouped_row_messages.append({
                    'msg': msg,
                    'row': self.to_dictionary(row),
                    'line': self.user_line_number
                })
            self._grouped_rows.append(self.to_dictionary(row))
            self._last_line_of_group += 1
            self._current_group_has_errors = True

        # except Exception as e: # We do not want to set current_group_has_errors for process_last_set_of_rows errors
        #     self._current_group_has_errors = True
        #     raise Exception(e, None, sys.exc_info()[2])

        else:
            if result.get('cleaned'):
                cleaned_data = result.get('data')
                self._group_cleaned_data.append(cleaned_data)
                #should be:
                # self._grouped_rows.append(cleaned_data)
                self._grouped_rows.append(self.to_dictionary(row))
                self._last_line_of_group += 1
            else:
                self._grouped_rows.append(self.to_dictionary(row))
                self._last_line_of_group += 1
                self._current_group_has_errors = True
                for data in result.get('data'):
                    self._grouped_row_messages.append({
                        'line': self.user_line_number,
                        'msg': data.get('error'),
                        'row': self.to_dictionary(row),
                        'field': data.get('field',),
                        'value': data.get('value')
                    })

    def save(self, cleaned_data):
        super(GroupNeoImporter, self).save(cleaned_data)
        if cleaned_data:
            raw_data = self.get_info_grouped(group=cleaned_data, character_for_join=None)
            self.report.add_info(raw_data)

    def get_info_grouped(self, group,
                         one_value_fields=[],
                         grouped_fields=[],
                         ignored_fields=[],
                         character_for_join='|',
                         user_labels=False):

        #this method merge all de data of one group

        grouped_fields = self.grouped_fields or grouped_fields

        if not grouped_fields:
            # Get all columns that ends with 'List'
            grouped_fields = [x for x in self.columns if x.endswith('List')]
        if not one_value_fields:
            # Get the others ones
            one_value_fields = [x for x in self.columns if x not in grouped_fields]

        # result will be a dict with all columns as a keys and "None" as values
        result = dict(zip(self.columns, [None] * len(self.columns)))

        for column in self.columns:
            if column in ignored_fields:
                result.pop(column)
                continue

            if column in one_value_fields:
                # for fields in one_value_fields we'll take the first value
                result[column] = group[0].get(column)
                continue

            if column in grouped_fields:
                values = []
                for group_item in group:
                    values.append(str(group_item.get(column)))
                if character_for_join is None:
                    # Save values as a list if no split character is defined
                    result[column] = values
                else:
                    result[column] = character_for_join.join(values)
                continue
        return result


def neo_data_importer_view_decorator(view, cacheable=False):
    """
    Decorator to create an admin view attached to this ``AdminSite``. This
    wraps the view and provides permission checking by calling
    ``self.has_permission``.

    You'll want to use this from within ``AdminSite.get_urls()``:

        class MyAdminSite(AdminSite):

            def get_urls(self):
                from django.conf.urls.defaults import patterns, url

                urls = super(MyAdminSite, self).get_urls()
                urls += patterns('',
                    url(r'^my_view/$', self.admin_view(some_view))
                )
                return urls

    By default, admin_views are marked non-cacheable using the
    ``never_cache`` decorator. If the view can be safely cached, set
    cacheable=True.
    """
    def inner(request, *args, **kwargs):
        user = request.user
        importer_class = kwargs.pop('importer_class')
        importer = importer_class(user=user, process_importer=kwargs.pop('process', False))

        if not user.has_perms(importer.get_permissions()):
            return HttpResponseForbidden()

        kwargs['importer'] = importer
    #     if not self.has_permission(request):
    #         return self.login(request)
        return view(request, *args, **kwargs)
    if not cacheable:
        inner = never_cache(inner)
    # We add csrf_protect here so this function can be used as a utility
    # function for any view, without having to repeat 'csrf_protect'.
    if not getattr(view, 'csrf_exempt', False):
        inner = csrf_protect(inner)
    return update_wrapper(inner, view)


class GroupNeoImporterWithRevision(GroupNeoImporter):
    result_helper = NeoResultHelper
    group_validations = []
    date_formats = ['%d.%m.%Y', '%d/%m/%Y', '%Y/%m/%d']
    importer_type = None
    columns_mapping = ()
    formset_params = None
    entity_name = None
    template_titles_line = 0
    custom_url_name = None
    app_label_url = 'importers'
    api_label_url = 'api'

    def __init__(self, reader=ExcelReaderAllAsString(encoding='utf-8'), process_importer=False, *args, **kwargs):

        super(GroupNeoImporterWithRevision, self).__init__(
            reader,
            *args,
            **kwargs
        )
        if self.importer_type is None:
            self.importer_type = self.__class__.__name__

        if self.entity_name is None:
            self.entity_name = self.importer_type
        # self.columns_mapping = (
        #     {
        #         'label': 'Text',             # template label
        #         'field_mapping': 'FB_text',  # Optional
        #         'index_to_group': True,             # For get index to group fields
        #         # 'extra_params': True,        # For get extra params
        #         'grouped_field': True,        # For get extra params
        #     },
        # )

        self.set_importer_options()
        self.template_name = kwargs.pop('template_name', self.__class__.__name__)

        self.process_importer = process_importer
        self.first_valid_line = 1
        self.validate_column_names = True

    def validate_template(self, file_imported):
        # Receive in memory file
        for line_number, row in ExcelReaderInMemoryAllAsString().lines(file_imported.read()):
            self.user_line_number = line_number + 1  # For displaying user messages, line starts in 1

            if line_number == self.template_titles_line and self.validate_column_names:
                self.validate_column_quantity(row)
                self.validate_with_template(row)
                break

            if line_number < self.first_valid_line:
                continue

    def execute_internal(self, data_source):
        self.pre_execute(data_source)

        if self.auto_assign_columns:
            self._auto_assign_columns(data_source)

        for line_number, row in self.reader.lines(data_source):
            self.user_line_number = line_number + 1  # For displaying user messages, line starts in 1

            if line_number == self.template_titles_line and self.validate_column_names:
                self.validate_column_quantity(row)
                self.validate_with_template(row)

            if line_number < self.first_valid_line:
                continue

            self.rows.append(row)
            try:
                self._current_group = self.get_current_group(row)
                # we ignore first line, but it need to take care files with only one line
                if not self._last_group:
                    self._last_group = self._current_group
                    self._first_line_of_group = self.user_line_number
                    self._last_line_of_group = self.user_line_number
                self.process_row(row)
            except ImporterError as e:
                e.exception_message = e.detailed_user_message()
                e.original_traceback = repr(traceback.format_exc())
                e.line_number = self.user_line_number
                e.row = row
                raise (e, None, sys.exc_info()[2])
            self.report.line_read()

        try:
            self.user_line_number += 1
            self.process_last_set_of_rows()
        except ImporterError as e:
            e.exception_message = e.detailed_user_message()
            e.original_traceback = repr(traceback.format_exc())
            e.line_number = self.user_line_number
            e.row = row
            raise (e, None, sys.exc_info()[2])

        self.post_execute(data_source)

    def validate_column_quantity(self, row):
        """If applicable, check if expected column quantity is equal to existent quantity.
        """

        column_quantity = len(self.columns_mapping)
        if column_quantity:
            clear_row = [i for i in row if i]
            if column_quantity != len(clear_row):
                errors = u'Invalid column quantity. Expected:%s - Existent:%s' % (column_quantity, len(clear_row))
                raise StopImporter(
                    u"You have uploaded a wrong or outdated template. {0}. Please, follow <a class='' href='{1}'>this template file</a> to avoid validation errors.".format(
                        errors,
                        self.get_importer_link()
                    )
                )

    def validate_with_template(self, row):
        """
        Check if the headers of the imported file is the same as the template file of the importer.
        """
        errors = []
        for column, index in zip(self.columns_label_mapping.values(), range(0, len(self.columns_label_mapping))):
            file_column = slugify(row[index].strip())
            template_column = slugify(column.strip())
            if file_column == template_column:
                continue

            else:
                errors.append(column)

        if errors:
            raise StopImporter(
                u"You have uploaded a wrong or outdated template. Missing columns: {0}. Please, follow <a class='' href='{1}'>this template file</a> to avoid validation errors.".format(
                    u', '.join(errors),
                    self.get_importer_link()
                )
            )

    def get_date(self, value):
        for d_format in self.date_formats:
            try:
                return datetime.strptime(value, d_format)
            except ValueError:
                pass
        try:
            import xlrd
            year, month, day, h, m, s = xlrd.xldate_as_tuple(int(value), 0)
            return datetime(day=day, month=month, year=year)
        except:
            pass
        return None

    def valid_template_name(self):
        if len(self.template_name) > 30:
            return self.template_name[:30]
        return self.template_name

    def generate_template_xls(self):
        header_fields = self.labels
        sheet_data = SheetData(self.valid_template_name())
        sheet_data.add_header(header_fields)
        excel_data = ExcelData()
        excel_data.add_sheet(sheet_data)
        return excel_data.get_workbook()

    def set_extra_options(self, column):
        pass

    def set_importer_options(self):
        self.columns = OrderedDict()
        self.indexes_of_key_columns_to_group = []
        self.labels = []
        self.grouped_fields = OrderedDict()
        self.columns_field_mapping = OrderedDict()
        self.columns_label_mapping = OrderedDict()
        self.columns_to_group = OrderedDict()
        self.validators = OrderedDict()
        index = 0

        for column in self.columns_mapping:
            label = column.get('label', None)
            index_to_group = column.get('index_to_group', False)
            grouped_field = column.get('grouped_field', False)
            field_mapping = column.get('field_mapping', slugify(label).replace('-', '_'))
            is_required = column.get('required', False)
            field_validators = column.get('validators', list())
            column['field_mapping'] = field_mapping

            if field_validators is not None and not isinstance(field_validators, (list, tuple)):
                field_validators = [field_validators]

            if is_required:
                field_validators.append(RequiredValidator(True))

            if label is None:
                raise Exception('Label is required for columns')

            if index_to_group:
                self.indexes_of_key_columns_to_group.append(index)
                self.columns_to_group[label] = field_mapping

            if grouped_field:
                self.grouped_fields[label] = field_mapping

            # if extra_param:
            #     extra_params.append(label)

            self.columns[field_mapping] = index
            self.columns_label_mapping[field_mapping] = label
            self.columns_field_mapping[label] = field_mapping
            self.validators[field_mapping] = field_validators
            self.labels.append(label)
            self.set_extra_options(column)

            index += 1

    # def pre_execute(self, data_source=None):
    #     self.queue = self.extra_user_params.get('queue', None)
    #     if self.queue == "":
    #         self.queue = None

    def group_clean(self, grouped_cleaned_data, grouped_rows=None):
        if grouped_rows:

            errors = []
            for validation in self.group_validations:
                try:
                    validation(grouped_cleaned_data, grouped_rows)
                except ValidationError as e:
                    errors.append(e.messages[0])
                if errors:
                    raise ValidationError(errors)

        return grouped_cleaned_data

    def get_info_grouped(self, group,
                         one_value_fields=[],
                         grouped_fields=[],
                         ignored_fields=[],
                         character_for_join='|',
                         user_labels=False):

        #this method merge all de data of one group

        grouped_fields = self.grouped_fields.values() or grouped_fields

        # if not grouped_fields:
        #     Get all columns that ends with 'List'
            # grouped_fields = [x for x in self.columns if x.endswith('List')]
        if not one_value_fields:
            # Get the others ones
            one_value_fields = [x for x in self.columns if x not in grouped_fields]

        # result will be a dict with all columns as a keys and "None" as values
        result = dict(zip(self.columns, [None] * len(self.columns)))

        for column in self.columns:
            if column in ignored_fields:
                result.pop(column)
                continue

            if column in one_value_fields:
                # for fields in one_value_fields we'll take the first value
                if isinstance(group, (list, tuple)) and len(group) > 0 :
                    result[column] = group[0][column]

                else:
                    result[column] = group[column]
                continue

            if column in grouped_fields:
                values = []
                for group_item in group:
                    if group_item.get(column) is not None:
                        values.append(str(group_item.get(column)))
                if character_for_join is None:
                    # Save values as a list if no split character is defined
                    result[column] = values
                else:
                    result[column] = character_for_join.join(values)
                continue
        return result

    def save_process_importer(self, cleaned_data):
        pass

    def execute(self, file_upload_history, extra_user_params={}, formset_params=None):
        self.file_upload_history = file_upload_history
        self.formset_params = formset_params
        super(GroupNeoImporterWithRevision, self).execute(file_upload_history, extra_user_params)

    def save_historic(self, file_upload_history, report):
        "We do not want to save start_execution_time, because this is not the 'real' importer"
          # must be unicode, not str
        if self.process_importer:
            file_upload_history.state = FileUploadHistory.PROCESSED
            file_upload_history.finish_execution_timestamp = datetime.now()

        else:
            file_upload_history.results = report.to_encoded_json()
            file_upload_history.start_execution_timestamp = None  # we do not want to mark this file as processed
            file_upload_history.finish_execution_timestamp = None  # we do not want to mark this file as processed
            file_upload_history.state = None  # we do not want to mark this file as processed

        file_upload_history.save()

    def get_results(self, fileuploadhistory):

        results = self.result_helper(
            grouped_fields=self.grouped_fields,
            columns_mapping=self.columns_field_mapping,
            columns_to_group=self.columns_to_group
        )
        # results.load_from_jobs(fileuploadhistory)
        results.load_from_json(fileuploadhistory.results)
        return results

    def get_redirect_url(self):
        return None

    @staticmethod
    def get_importer_link():
        return None

    @staticmethod
    def get_api_importer_link():
        return None

    def get_current_group(self, row):
        "It iterates all key columns and create a list with its values"
        current_group = []
        if self.indexes_of_key_columns_to_group:
            for column in self.indexes_of_key_columns_to_group:
                current_group.append(row[column])

        else:
            current_group = [self.user_line_number]
        return current_group

    @classmethod
    def get_permission(cls):
        permission, created = Permission.objects.get_or_create(
            content_type=cls.get_content_type(),
            codename=cls.get_permission_codename(),
            defaults={
                'name': cls.get_permission_name(),
            }
        )

        return permission

    @classmethod
    def get_permission_code(cls):
        permission = cls.get_permission()

        return u'{0}.{1}'.format(
            permission.content_type.app_label,
            permission.codename
        )

    @classmethod
    def get_permissions(cls):
        return [cls.get_permission_code()]

    @classmethod
    def get_content_type(cls):
        return ContentType.objects.get_for_model(FileUploadHistory())

    @classmethod
    def get_permission_name(self):
        return u'Importer {0}'.format(self.get_importer_type())

    @classmethod
    def get_permission_codename(self):
        return u'importer_revision__{0}'.format(slugify(self.get_importer_type()).replace('-', '_'))

    def clean(self, row):
        """
        Clean all the fields in the 'row' dictionary by calling a 'validate_key' method,
        where 'key' is the 'key' from dictionary. The validate method must the defined
        in the class that inherit this one.
        """
        row = self.pre_clean(row)
        if row is None:
            raise ImporterError('The pre_clean must return a valid row!')
        try:
            self.validate_row_length(row)
        except InvalidLength:
            self.add_error(u'Line: %s: Invalid row length found (%s) valid is %s' %
                            (self.user_line_number, len(row), str(self.valid_row_lengths)), row)
            return

        if not isinstance(row, dict):
            mapped_row = self.to_dictionary(row)
        else:
            mapped_row = row

        result = self.validate_fields(mapped_row)
        result['original_data'] = mapped_row

        if result.get('cleaned'):
            result['data'] = self.post_clean(result.get('data'))
        if result.get('data') is None:
            raise Exception('The post_clean must return a valid row!') # this is a programming error
        return result

    # def process_row(self, row):
    #     try:
    #         cleaned_data = self.clean(row)
    #         self.save(cleaned_data)
    #         return cleaned_data
    #     except SkipRow:
    #         return
    #     except (ValidationError, ImporterWarning) as e:
    #         if hasattr(e, 'messages') and e.messages:
    #             for error in e.messages:
    #                 try:
    #                     self.add_error(u'Line %s: %s' % (self.user_line_number, error), row)
    #                 except UnicodeDecodeError:
    #                     self.add_error(u'[line:%s] This line was not imported because some characters \
    #                                               could not be interpreted.' % self.user_line_number)
    #         else:
    #             try:
    #                 self.add_error(u'Line %s: %s' % (self.user_line_number, e), row)
    #             except UnicodeDecodeError:
    #                 self.add_error(u'Line %s: This line was not imported because some characters \
    #                                           could not be interpreted.' % self.user_line_number)

    # def save(self, cleaned_data):
    #     if self.process_importer:
    #         self.all_cleaned_data.append(cleaned_data)
    #         self.save_process_importer(cleaned_data)
    #
    #     else:
    #         super(GroupNeoImporterWithRevision, self).save(cleaned_data)

    def save(self, cleaned_data):
        self.all_cleaned_data.append(cleaned_data)
        if self.process_importer:
            if not self.indexes_of_key_columns_to_group:
                cleaned_data = self.get_info_grouped(group=cleaned_data, character_for_join=None)
            self.save_process_importer(cleaned_data)

        raw_data = self.get_info_grouped(group=self._grouped_rows, character_for_join=None)
        raw_data['importer_extra_data'] = {
            'user_line_number': self.user_line_number - 1
        }
        self.report.add_info(raw_data)

    def get_results_template(self):
        return 'data_importer/neo_file_importer_show_results.html'

    def get_form_template(self):
        return 'data_importer/neo_file_importer_with_revision.html'

    def get_show_validations_template(self):
        return 'data_importer/neo_file_importer_show_validations.html'

    # @classmethod
    # def get_url(cls):
    #     from django.conf.urls.defaults import url
    #     return url(
    #         cls.get_url_pattern(),
    #         cls.get_importer_view(),
    #         cls.get_url_kwargs(),
    #         name=cls.get_url_name()
    #     )

    @classmethod
    def wrap(cls, view):
        def wrapper(*args, **kwargs):
            return neo_data_importer_view_decorator(view)(*args, **kwargs)

        return update_wrapper(wrapper, view)

    @classmethod
    def get_urls(cls):
        from django.conf.urls import url

        urlpatterns = (
            # cls.get_url(),
            url(r'^%s/%s/upload-file/$' % (cls.get_app_label_url(), cls.get_custom_url()),
                cls.wrap(cls.upload_file_view),
                cls.get_kwargs(),
                name='%s_upload_file' % cls.get_url_name()
            ),
            url(r'^%s/%s/download-template/$' % (cls.get_app_label_url(), cls.get_custom_url()),
                cls.wrap(cls.download_template_file_view),
                cls.get_kwargs(),
                name='%s_download_template' % cls.get_url_name()
            ),
            url(
                r'^%s/%s/validate-file/(?P<file_id>\d+)/$' % (cls.get_app_label_url(), cls.get_custom_url()),
                cls.wrap(cls.validate_file_view),
                cls.get_kwargs(),
                name='%s_validate_file' % cls.get_url_name()
            ),
            url(
                r'^%s/%s/process-file/(?P<file_id>\d+)/$' % (
                cls.get_app_label_url(), cls.get_custom_url()),
                cls.wrap(cls.process_file_view),
                cls.get_kwargs_process(),
                name='%s_process_file' % cls.get_url_name()
            ),
            url(
                r'^%s/%s/results-file/(?P<file_id>\d+)/$' % (
                    cls.get_app_label_url(), cls.get_custom_url()),
                cls.wrap(cls.results_file_view),
                cls.get_kwargs_results(),
                name='%s_results_file' % cls.get_url_name()
            ),
            # url(r'^(.+)/history/$',
            #     wrap(self.history_view),
            #     name='%s_%s_history' % info),
            # url(r'^(.+)/delete/$',
            #     wrap(self.delete_view),
            #     name='%s_%s_delete' % info),
            # url(r'^(.+)/$',
            #     wrap(self.change_view),
            #     name='%s_%s_change' % info),
        )
        return urlpatterns

    @classmethod
    def get_api_urls(cls):
        from django.conf.urls import url

        urlpatterns = (
            url(r'^%s/%s/%s/upload-file/$' % (cls.get_app_label_url(), cls.get_api_label_url(), cls.get_custom_url()),
                # cls.wrap(cls.api_upload_file_view),
                cls.wrap(UploadFileApiView.as_view()),
                cls.get_kwargs(),
                name='%s_api_upload_file' % cls.get_url_name()
                ),
            url(r'^%s/%s/%s/download-template/$' % (cls.get_app_label_url(), cls.get_api_label_url(), cls.get_custom_url()),
                cls.wrap(cls.download_template_file_view),
                cls.get_kwargs(),
                name='%s_api_download_template' % cls.get_url_name()
                ),
            url(r'^%s/%s/%s/information/$' % (cls.get_app_label_url(), cls.get_api_label_url(), cls.get_custom_url()),
                cls.wrap(ImporterInformationApiView.as_view()),
                cls.get_kwargs(),
                name='%s_api_information' % cls.get_url_name()
                ),
            url(
                r'^%s/%s/%s/(?P<pk>\d+|__pk__)/$' % (cls.get_app_label_url(),  cls.get_api_label_url(), cls.get_custom_url()),
                cls.wrap(DetailFileHistoryApiView.as_view()),
                cls.get_kwargs(),
                name='%s_api_detail_file' % cls.get_url_name()
            ),
            url(
                r'^%s/%s/%s/(?P<pk>\d+|__pk__)/validate-file/$' % (cls.get_app_label_url(),  cls.get_api_label_url(), cls.get_custom_url()),
                cls.wrap(ValidateFileHistoryApiView.as_view()),
                cls.get_kwargs(),
                name='%s_api_validate_file' % cls.get_url_name()
            ),
            url(
                r'^%s/%s/%s/(?P<pk>\d+|__pk__)/process-file/$' % (
                    cls.get_app_label_url(), cls.get_api_label_url(), cls.get_custom_url()),
                cls.wrap(ProcessFileHistoryApiView.as_view()),
                cls.get_kwargs_process(),
                name='%s_api_process_file' % cls.get_url_name()
            ),
            url(
                r'^%s/%s/%s/(?P<pk>\d+|__pk__)/results-file/$' % (
                    cls.get_app_label_url(), cls.get_api_label_url(), cls.get_custom_url()),
                cls.wrap(ResultsFileHistoryApiView.as_view()),
                cls.get_kwargs_results(),
                name='%s_api_results_file' % cls.get_url_name()
            ),
            # url(r'^(.+)/history/$',
            #     wrap(self.history_view),
            #     name='%s_%s_history' % info),
            # url(r'^(.+)/delete/$',
            #     wrap(self.delete_view),
            #     name='%s_%s_delete' % info),
            # url(r'^(.+)/$',
            #     wrap(self.change_view),
            #     name='%s_%s_change' % info),
        )
        return urlpatterns

    @classmethod
    def process_file_view(cls, request, file_id, **kwargs):
        importer = kwargs.get('importer')
        file_upload_history = get_object_or_404(
            FileUploadHistory,
            id=file_id,
            type=importer.get_importer_type()
        )

        if request.method == 'POST':
            form_class = importer.get_form()
            formset_class = importer.get_formset_class()

            valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

            data = file_upload_history.get_form_params()
            form = form_class(valid_extensions, request.user, data=data, no_validate_file=True)
            form.is_valid()

            formset_cleaned_data = None
            if formset_class:
                formset = formset_class(data=data)
                formset.is_valid()
                formset_cleaned_data = formset.cleaned_data

            importer.execute(
                file_upload_history,
                extra_user_params=form.cleaned_data,
                formset_params=formset_cleaned_data
            )

            messages.success(request, 'File successfully processed')
            return redirect(importer.get_results_file_url(file_upload_history.id))

        else:
            return redirect(importer.get_absolute_url())

    @classmethod
    def results_file_view(cls, request, file_id, **kwargs):
        importer = kwargs.get('importer')
        file_upload_history = get_object_or_404(
            FileUploadHistory,
            id=file_id,
            type=importer.get_importer_type()
        )

        template = importer.get_results_template()
        results = importer.get_results(file_upload_history)
        importer.file_upload_history = file_upload_history
        kwargs['results'] = results
        kwargs['file_upload_history'] = file_upload_history
        kwargs['entity_name'] = importer.entity_name
        kwargs['importer_title'] = importer.get_importer_title()
        kwargs['importer_type'] = importer.get_importer_type()
        kwargs['upload_file_url'] = importer.get_upload_file_url()
        kwargs['process_file_url'] = importer.get_process_file_url(file_upload_history.id)
        kwargs['importer'] = importer

        return render(request, template, kwargs)

    @classmethod
    def validate_file_view(cls, request, file_id, **kwargs):
        importer = kwargs.get('importer')
        file_upload_history = get_object_or_404(
            FileUploadHistory,
            id=file_id,
            type=importer.get_importer_type()
        )

        form_class = importer.get_form()
        formset_class = importer.get_formset_class()

        valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        data = file_upload_history.get_form_params()
        form = form_class(valid_extensions, request.user, data=data, no_validate_file=True)
        form.is_valid()

        formset_cleaned_data = None
        formset = None
        if formset_class:
            formset = formset_class(data=data)
            formset.is_valid()
            formset_cleaned_data = formset.cleaned_data

        importer.execute(
            file_upload_history,
            extra_user_params=form.cleaned_data,
            formset_params=formset_cleaned_data
        )

        results = importer.get_results(file_upload_history)
        template = importer.get_show_validations_template()
        kwargs['results'] = results
        kwargs['file_upload_history'] = file_upload_history
        kwargs['form'] = form
        kwargs['formset'] = formset
        kwargs['entity_name'] = importer.entity_name
        kwargs['importer_title'] = importer.get_importer_title()
        kwargs['importer_type'] = importer.get_importer_type()
        kwargs['upload_file_url'] = importer.get_upload_file_url()
        kwargs['process_file_url'] = importer.get_process_file_url(file_upload_history.id)

        return render(request, template, kwargs,)

    @classmethod
    def download_template_file_view(cls, request, **kwargs):
        " Needs description"

        importer = kwargs.get('importer')
        return cls.xls_response(importer.generate_template_xls(), '%s.xls' % importer.template_name)

    @staticmethod
    def xls_response(workbook, filename=None):
        response = HttpResponse(content_type="application/ms-excel")
        if filename:
            response['Content-Disposition'] = 'attachment; filename="%s"' % filename
        workbook.save(response)
        return response

    @classmethod
    def upload_file_view(cls, request, **kwargs):
        " Needs description"

        importer = kwargs.get('importer')

        form_class = importer.get_form()
        formset_class = importer.get_formset_class()

        valid_extensions = kwargs.pop('valid_extensions', ['xls', 'xlsx'])

        # template_file = kwargs.get('template_file', importer.get_importer_link())
        # kwargs['template_file'] = template_file
        kwargs['importer_type'] = importer.get_importer_type()
        kwargs['entity_name'] = importer.entity_name
        kwargs['importer_title'] = importer.get_importer_title()
        kwargs['title'] = importer.get_importer_title()
        if importer.get_html_helper_messages():
            kwargs['html_messages'] = importer.get_html_helper_messages()
        template = importer.get_form_template()

        success_message = kwargs.pop('success_message', 'File imported with success.')
        if request.method == 'POST':
            form = form_class(
                valid_extensions,
                request.user,
                request.POST,
                request.FILES,
                process_importer=False,
                importer=importer
            )
            if formset_class:
                formset = formset_class(request.POST, request.FILES)
                formset_valid = formset.is_valid()

            else:
                formset = None
                formset_valid = True

            if form.is_valid() and formset_valid:
                file_upload_history = form.save(commit=False)
                file_upload_history.type = importer.get_importer_type()
                file_upload_history.user = request.user
                file_upload_history.set_form_params(request.POST)

                file_upload_history.save()

                return redirect(reverse(u'importers:{0}_validate_file'.format(importer.get_url_name()), args=(file_upload_history.id, )))

            else:
                pass

        else:
            form = form_class(valid_extensions, request.user)
            if formset_class is not None:
                formset = formset_class()

            else:
                formset = None

        kwargs['formset'] = formset
        kwargs['form'] = form
        kwargs['template_file_url'] = importer.get_template_file_url()

        return render(request, template, kwargs)

    @classmethod
    def get_url_kwargs(cls):
        kwargs = {
            'importer_class': cls,
        }

        return kwargs

    @classmethod
    def get_kwargs(cls):
        kwargs = {
            'importer_class': cls,
        }

        return kwargs

    @classmethod
    def get_kwargs_process(cls):
        kwargs = cls.get_kwargs()
        kwargs['process'] = True

        return kwargs

    @classmethod
    def get_kwargs_results(cls):
        kwargs = cls.get_kwargs()
        return kwargs

    @classmethod
    def get_form(cls):
        return NeoFileImporterForm

    @classmethod
    def get_serializer_class(cls):
        return NeoFileImporterSerializer

    def get_formset_class(self):
        return None

    @classmethod
    def get_importer_type(cls):
        return cls.importer_type if cls.importer_type is not None else cls.__name__

    # @classmethod
    # def get_url_pattern(cls):
    #     if cls.custom_url_name:
    #         app_label = cls.__module__.split('.')[0]
    #         return r'^{0}/{1}/$'.format(app_label, cls.get_custom_url())
    #     return r'^importers/importer-{0}/$'.format())

    @classmethod
    def get_custom_url(cls):
        custom_url = cls.custom_url_name or cls.get_importer_type()

        return slugify(custom_url)

    @classmethod
    def get_app_label_url(cls):
        app_label_url = cls.app_label_url or cls.__module__.split('.')[0]

        return slugify(app_label_url)

    @classmethod
    def get_api_label_url(cls):
        return slugify(cls.api_label_url)

    @classmethod
    def get_url_name(cls):
        return '{0}'.format(slugify(cls.get_importer_type()).replace('-', '_'))

    @classmethod
    def get_importer_title(cls):
        return 'Importer {0}'.format(cls.get_importer_type())

    @classmethod
    def get_importer_menu_title(cls):
        return cls.get_importer_title()

    @classmethod
    def get_importer_menu_template(cls):
        return 'data_importer/_neo_importer_menu_link.html'

    @classmethod
    def get_importer_view(cls):
        return 'data_importer.views.neo_file_importer'

    @classmethod
    def get_absolute_url(cls):
        return cls.get_upload_file_url()

    @classmethod
    def get_upload_file_url(cls):
        return reverse('importers:{0}_upload_file'.format(cls.get_url_name()))

    @classmethod
    def get_template_file_url(cls):
        if cls.get_importer_link():
            return cls.get_importer_link()
        return reverse('importers:{0}_download_template'.format(cls.get_url_name()))

    @classmethod
    def get_process_file_url(cls, file_upload_id):
        return reverse('importers:{0}_process_file'.format(cls.get_url_name()), args=(file_upload_id, ))

    @classmethod
    def get_results_file_url(cls, file_upload_id):
        return reverse('importers:{0}_results_file'.format(cls.get_url_name()), args=(file_upload_id, ))

    @classmethod
    def get_html_helper_messages(cls):
        return None

    @classmethod
    def get_api_template_file_url(cls):
        if cls.get_api_importer_link():
            return cls.get_api_importer_link()
        return reverse('api_importers:{0}_api_download_template'.format(cls.get_url_name()))

    @classmethod
    def get_api_upload_file_url(cls):
        return reverse('api_importers:{0}_api_upload_file'.format(cls.get_url_name()))

    @classmethod
    def get_api_process_file_url(cls, file_upload_id):
        return reverse('api_importers:{0}_api_process_file'.format(cls.get_url_name()), args=(file_upload_id,))

    @classmethod
    def get_api_results_file_url(cls, file_upload_id):
        return reverse('api_importers:{0}_api_results_file'.format(cls.get_url_name()), args=(file_upload_id,))

    @classmethod
    def get_api_validate_file_url(cls, file_upload_id):
        return reverse('api_importers:{0}_api_validate_file'.format(cls.get_url_name()), args=(file_upload_id,))

    @classmethod
    def get_api_detail_file_url(cls, file_upload_id):
        return reverse('api_importers:{0}_api_detail_file'.format(cls.get_url_name()), args=(file_upload_id,))
