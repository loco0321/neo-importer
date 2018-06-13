# -*- coding: utf-8 -*-
import csv
from datetime import datetime, time
from xlrd import open_workbook, xldate, xldate_as_tuple, XL_CELL_EMPTY, XL_CELL_TEXT, XL_CELL_NUMBER, \
                 XL_CELL_DATE, XL_CELL_BOOLEAN, XL_CELL_BLANK
from xlrd.biffh import XLRDError

import logging

from neo_importer.exceptions import ImporterError
from neo_importer import utils


class Reader(object):

    def is_empty_line(self, values):
        for v in values:
            if v:
                return False
        return True

    def lines(self, data_source):
        "Receive a data_source, for example, a file or a variable, and return a list (generator) of data"
        return 0, {} # this reader can be used to ignore the default behavior of the data importer


class ExcelReader(Reader):
    def __init__(self, encoding='cp1252', sheet_index=0):
        """
        examples of encodings: iso-8859-1, utf-8 or cp1252
        """
        self.encoding = encoding
        self.sheet_index = sheet_index

    def _format_values(self, values, types, convert_to_string=False):
        for i, v in enumerate(values):
            if types[i] == XL_CELL_TEXT: # str
                # excel special behavior: 1 is converted to str, not int
                # excel special behavior: 1,2 is converted to str, not float
                if not convert_to_string:
                    try:
                        int(v)
                        if ',' not in values[i]: # this is not a float
                            values[i] = int(v)
                    except: # this is not a int, lets try with float now...
                        try:
                            v = v.replace(',' , '.')
                            values[i] = float(v)
                        except: # this is not a float, let this as string
                            pass
            elif types[i] == XL_CELL_NUMBER: # float (number)
                if int(v) == v: # int number
                    values[i] = int(v)
            elif types[i] == XL_CELL_DATE: # float (date)
                try:
                    date_args = xldate_as_tuple(v, 0) # datemode = 0 (1900-based)
                    try:
                        values[i] = datetime(*date_args)
                        if convert_to_string:
                            values[i] = values[i].strftime('%Y/%m/%d')
                    except ValueError:
                        # table cells with time only
                        values[i] = time(*date_args[3:])
                        if convert_to_string:
                            values[i] = values[i].strftime('%H/%M')
                except xldate.XLDateAmbiguous:
                    pass
            elif types[i] == XL_CELL_BOOLEAN: # int (boolean)
                values[i] = True if v == 1 else False
        if convert_to_string:
            values = list(map(utils.handle_string, values))
        return values

    def is_empty_line(self, types):
        for type in types:
            if type != XL_CELL_EMPTY and type != XL_CELL_BLANK:
                return False
        return True

    def lines(self, data_source):
        "data_source must be a filepath"
        try:
            book = open_workbook(filename=data_source, encoding_override=self.encoding)
        except XLRDError:
            raise ImporterError('Unsupported format, or corrupt file. Is it a valid XLS?')
        sheet = book.sheet_by_index(self.sheet_index)
        for row_number in range(0, sheet.nrows):  # Ignores the header
            types = sheet.row_types(row_number)
            if self.is_empty_line(types):
                continue

            values = sheet.row_values(row_number)
            values = self._format_values(values, types)
            yield row_number, values


class ExcelReaderAllAsString(ExcelReader):
    def lines(self, data_source):
        "data_source must be a filepath"
        try:
            book = open_workbook(filename=data_source, encoding_override=self.encoding, formatting_info=True)
        except NotImplementedError:
            book = open_workbook(filename=data_source, encoding_override=self.encoding)
        except XLRDError:
            raise ImporterError('Unsupported format, or corrupt file. Is it a valid XLS?')
        sheet = book.sheet_by_index(self.sheet_index)
        for row_number in range(0, sheet.nrows):  # Ignores the header
            types = sheet.row_types(row_number)
            if self.is_empty_line(types):
                continue

            values = sheet.row_values(row_number)

            #The proper way to do this is reading the excel format:
            #http://groups.google.com/group/python-excel/browse_thread/thread/2d07febfa031dfa5
            #cells = sheet.row(row_number)
            #formats = [book.format_map[book.xf_list[cell.xf_index].format_key].format_str for cell in cells]
            values = self._format_values(values, types, True)
            yield row_number, values


class ExcelReaderInMemoryAllAsString(ExcelReader):
    def lines(self, data_source):
        "data_source must be a filepath"
        try:
            book = open_workbook(file_contents=data_source, encoding_override=self.encoding, formatting_info=True)
        except NotImplementedError:
            book = open_workbook(file_contents=data_source, encoding_override=self.encoding)
        except XLRDError:
            raise ImporterError('Unsupported format, or corrupt file. Is it a valid XLS?')
        sheet = book.sheet_by_index(self.sheet_index)
        for row_number in range(0, sheet.nrows):  # Ignores the header
            types = sheet.row_types(row_number)
            if self.is_empty_line(types):
                continue

            values = sheet.row_values(row_number)

            #The proper way to do this is reading the excel format:
            #http://groups.google.com/group/python-excel/browse_thread/thread/2d07febfa031dfa5
            #cells = sheet.row(row_number)
            #formats = [book.format_map[book.xf_list[cell.xf_index].format_key].format_str for cell in cells]
            values = self._format_values(values, types, True)
            yield row_number, values


class CSVFileReader(Reader):
    def __init__(self, encoding='iso-8859-1', delimiter='\t'):
        """
        examples of encodings: iso-8859-1, utf-8 or cp1252
        examples of delimiters: \t ; ,
        """
        self.encoding = encoding
        self.delimiter = delimiter

    @staticmethod
    def to_unicode(value, encoding):
        """
        Receive string value and try to return a utf-8 string.
        """
        value = value.strip()
        logger = logging.getLogger('Data_importer.CSVFileReader')

        try:
            return value.decode(encoding)
        except Exception as e:
            logger.error('cant decode: \n %s' % e)
            try:
                return value.decode('cp1252')
            except Exception as e:
                logger.error('cant decode to cp1252: \n %s' % e)

        return value

    def lines(self, data_source):
        "data_source must be a filepath"
        from django.conf import settings
        import os
        target_file_name = os.path.join(settings.TEMP_PATH, os.path.basename(data_source))

        try:
            with open(data_source, 'r') as source_file:
                with open(target_file_name, 'w') as dest_file:
                    contents = source_file.read()
                    dest_file.write(contents.decode(self.encoding).encode('utf-8'))
        except UnicodeDecodeError:
            with open(data_source, 'rb') as source_file:
                with open(target_file_name, 'w') as dest_file:
                    contents = source_file.read()
                    dest_file.write(contents.decode(self.encoding).encode('utf-8'))

        with open(target_file_name, 'r') as this_file:

            first_line = this_file.readline()

            if self.delimiter not in first_line and '\n' not in first_line:
                # In excel, there are 3 ways to save as CSV: one of them is invalid and raise 500 error (MacIntosh CSV)
                # Here we are validating if the CSV file is valid
                raise ImporterError('Invalid CSV format. In excel, please use Save as > Other formats > CSV (Comma delimited) (*.csv).')

            # restart file
            this_file.seek(0)

            for row_number, row in enumerate(this_file):
                values = [self.to_unicode(value, 'utf-8') for value in row.split(self.delimiter)]
                if self.is_empty_line(values):
                    continue
                yield row_number, values


class CustomDictReader(csv.DictReader):
    """
    We Must override the next method to use SortedDict instead the default dict,
    so we can store the order the elements in the dictionary
    """
    def next(self):
        if self.line_num == 0:
            # Used only for its side effect.
            self.fieldnames
        row = self.reader.next()
        self.line_num = self.reader.line_num

        # unlike the basic reader, we prefer not to return blanks,
        # because we will typically wind up with a dict full of None
        # values
        while row == []:
            row = self.reader.next()
        #d = dict(zip(self.fieldnames, row))
        d = SortedDict(zip(self.fieldnames, row))
        lf = len(self.fieldnames)
        lr = len(row)
        if lf < lr:
            d[self.restkey] = row[lf:]
        elif lf > lr:
            for key in self.fieldnames[lr:]:
                d[key] = self.restval
        return d


class AutoCSVReader(Reader):

    def __init__(self, encoding='cp1252'):
        self.encoding = encoding

    def lines(self, data_source):
        "data_source must be a filepath"
        with open(data_source, 'r') as the_file:
            dialect = csv.Sniffer().sniff(the_file.readline())
            the_file.seek(0)
            lines = CustomDictReader(the_file, dialect=dialect)
            for row_number, dict_row in enumerate(lines):
                values = []
                for value in dict_row.values():
                    if isinstance(value, (str, unicode)):
                        values.append(value.strip().decode(self.encoding))
                    else:  # list: columns with the same name
                        list_of_values = []
                        for v in value:
                            list_of_values.append(v.strip().decode(self.encoding))
                        values.append(list_of_values)
                if self.is_empty_line(values):
                    continue
                yield row_number, values


class DefinedCSVReader(Reader):
    def __init__(self, name, delimiter, encoding='cp1252', **kwargs):
        self.name = name
        self.delimiter = delimiter
        self.encoding = encoding
        self.dialect_kwargs = kwargs

    def lines(self, data_source):
        "data_source must be a filepath"

        csv.register_dialect(self.name, delimiter=self.delimiter, **self.dialect_kwargs)

        with open(data_source, 'r') as the_file:
            lines = CustomDictReader(the_file, dialect=self.name)

            for row_number, dict_row in enumerate(lines):
                values = []
                for value in dict_row.values():
                    if isinstance(value, (str, unicode)):
                        values.append(value.strip().decode(self.encoding))
                    else: # list: columns with the same name
                        list_of_values = []
                        for v in value:
                            list_of_values.append(v.strip().decode(self.encoding))
                        values.append(list_of_values)
                if self.is_empty_line(values):
                    continue
                yield row_number, values
