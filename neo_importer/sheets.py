# -*- coding: utf-8 -*-
from copy import copy
import datetime
import string

import xlrd
from xlwt import easyxf, Workbook


# NSN Colors
# more info in xlwt/Style.py file

class ExcelCellStyle(object):
    def __init__(self, font_color='black', bold=True, vertical=False,
                 alignment='center', background_color='white', border=False):
        self.font_color = font_color
        self.bold = bold
        self.vertical = vertical
        self.alignment = alignment
        self.background_color = background_color
        self.border = border

    def background_hexadecimal_to_excel_color(self, hexadecimal):
        if hexadecimal == '#C0C0C0':
            return 'gray25'
        elif hexadecimal == '#808080':
            return 'gray50'
        elif hexadecimal == '#333333':
            return 'gray80'
        elif hexadecimal == '#800080':
            return 'violet'
        elif hexadecimal == '#FF9900':
            return 'light_orange'
        elif hexadecimal == '#FFCC00':
            return 'gold'

    def get_style_str(self):
        style = ''
        style += 'font: name Arial, color %s, bold %s;' % (self.font_color, self.bold)
        if self.vertical:
            style += 'alignment: horizontal %s, rotation 90;' % (self.alignment)
        else:
            style += 'alignment: horizontal %s;' % (self.alignment)
        if self.border:
            style += 'borders: left thin, right thin, top thin, bottom thin;'
        style += 'pattern: pattern solid, fore_colour %s;' % self.background_hexadecimal_to_excel_color(self.background_color)
        return style


class NSNTheme(object):
    @classmethod
    def yellow_black(cls, vertical=False):
        return ExcelCellStyle(font_color='black', background_color='#FFCC00', vertical=vertical)

    @classmethod
    def orange_black(cls, vertical=False):
        return ExcelCellStyle(font_color='black', background_color='#FF9900', vertical=vertical)

    @classmethod
    def purple_white(cls, vertical=False):
        return ExcelCellStyle(font_color='white', background_color='#800080', vertical=vertical)

    @classmethod
    def darkgray_white(cls, vertical=False):
        return ExcelCellStyle(font_color='white', background_color='#333333', vertical=vertical)

    @classmethod
    def midgray_black(cls, vertical=False):
        return ExcelCellStyle(font_color='white', background_color='#808080', vertical=vertical)

    @classmethod
    def lightgray_black(cls, vertical=False):
        return ExcelCellStyle(font_color='black', background_color='#C0C0C0', vertical=vertical)

    @classmethod
    def primary_colors(cls):
        return [NSNTheme.yellow_black(), NSNTheme.orange_black(), NSNTheme.purple_white()]

    @classmethod
    def secondary_colors(cls):
        return [NSNTheme.darkgray_white(), NSNTheme.midgray_black(), NSNTheme.lightgray_black()]

    @classmethod
    def all_colors(cls):
        return reduce(lambda x, y: x.extend(y) or x, [NSNTheme.primary_colors(), NSNTheme.secondary_colors()])


DEFAULT_STYLE = easyxf()
DEFAULT_HEADER = NSNTheme.darkgray_white()


class ExcelCell(object):
    def __init__(self, data='', style=DEFAULT_STYLE, col_span=1, row_span=1, ignored=False):
        self.data = data
        self.style = style
        self.col_span = col_span
        self.row_span = row_span
        self.ignored = ignored

    def __eq__(self, that):
        return self.data == that.data

    def __str__(self):
        return str(self.data)

    def decode_data(self, encoding):
        if self.data is not None and isinstance(self.data, str):
            self.data = self.data.decode(encoding)


class SheetData(object):
    """
    Store data to be used by an SheetGenerator.
    """

    def __init__(self, sheet_name, orientation='row'):
        self.sheet_name = sheet_name
        self._data = []  # Contains a list of data or a list of ExcelCell (that contains the data)
        self.orientation = orientation
        self.expanded_column_count = 0
        self.expanded_row_count = 0

    def __eq__(self, that):
        return self._data == that._data

    def __str__(self):
        return str(self._data)

    def _maybe_set_expanded_column_count(self, column_count):
        if column_count > self.expanded_column_count:
            self.expanded_column_count = column_count

    def overwrite_data(self, new_data):
        'new_data must be a list of lists'
        self._data = new_data

        self.expanded_column_count = 0
        self.expanded_row_count = 0

        for row in new_data:
            self.expanded_row_count += 1
            self._maybe_set_expanded_column_count(len(row))

    def add_cell_list_with_style(self, data_set, style, append_in_the_beginning=False):
        cells = []
        for data in data_set:
            if isinstance(data, ExcelCell):
                cells.append(data)
            else:
                cells.append(ExcelCell(data, style=style))
        if append_in_the_beginning:
            self._data.insert(0, cells)
        else:
            self._data.append(cells)

        self.expanded_row_count += 1

        self._maybe_set_expanded_column_count(len(data_set))

    def add_header(self, data_set, style=DEFAULT_HEADER, append_in_the_beginning=False):
        'data_set must be a list of data.'

        self.add_cell_list_with_style(data_set, style, append_in_the_beginning)

    def add_cell_list(self, data_set, append_in_the_beginning=False):
        'data_set may be a list of data or a list of ExcelCell.'
        if append_in_the_beginning:
            self._data.insert(0, data_set)
        else:
            self._data.append(data_set)

        self.expanded_row_count += 1

        self._maybe_set_expanded_column_count(len(data_set))

    def data(self):
        return self._data

    def decode_all_data(self, encoding):
        for cell_list in self._data:
            for cell in cell_list:
                if isinstance(cell, ExcelCell):
                    cell.decode_data(encoding)
                else:
                    if cell is not None and isinstance(cell, str):
                        cell = cell.decode(encoding)

    def append_sheet_data(self, sheet_data):
        for sheet_data_list in sheet_data.data():
            self._data.append(sheet_data_list)


class ExcelData(object):
    def __init__(self):
        self._sheets_data = []

    def __eq__(self, that):
        return self._sheets_data == that._sheets_data

    def __str__(self):
        return str(self._sheets_data)

    def add_sheet(self, sheet_data):
        self._sheets_data.append(sheet_data)

    def sheets(self):
        return self._sheets_data

    def decode_all_data(self, encoding):
        for sheet in self._sheets_data:
            sheet.decode_all_data(encoding)

    def get_sheet_by_name(self, name):
        for sheet_data in self.sheets():
            if sheet_data.sheet_name == name:
                return sheet_data
        return None

    def append_excel_data(self, excel_data):
        for sheet_data in excel_data.sheets():
            sheet = self.get_sheet_by_name(sheet_data.sheet_name)
            if sheet:
                sheet.append_sheet_data(sheet_data)
            else:
                self.add_sheet(sheet_data)

    def get_workbook(self):
        excel_generator = ExcelGenerator()
        return excel_generator.generate(self)


class SheetLogger(object):
    def error(self, error, row):
        pass

    def success(self, row):
        pass

    def info(self, row):
        pass


class NoSheetBoundariesError(Exception):
    pass


class SheetParser(object):
    def __init__(self, reader, logger=None):
        self.reader = reader
        self.current_row = None
        self.logger = logger if logger is not None else SheetLogger()

    def assert_preconditions(self):
        pass

    def boolean_or_none(self, field_value):
        current_option = str(field_value or '').strip().lower()
        if current_option == 'yes':
            return True
        elif current_option == 'no':
            return False
        return None

    def boolean_value_for(self, field_name):
        field_value = self.field_value_for(field_name)
        current_option = str(field_value or '').strip().lower()
        if current_option == 'yes':
            return True
        return False

    def field_exists(self, field_name):
        return self.current_row.get(field_name) is not None

    def field_is_checked(self, field_name, selected_row_pattern):
        field_value = self.stripped_value_for(field_name)
        return selected_row_pattern.search(field_value) is not None

    def field_value_for(self, field_name):
        return self.current_row[field_name]

    def field_as_datetime(self, field_name, format='%d/%m/%Y'):
        field_value = self.stripped_value_for(field_name)
        return self.value_to_datetime(field_value, format)

    def import_row(self):
        raise NotImplementedError('All importers must implement import_row() method')

    def import_sheet(self):
        self.assert_preconditions()
        for row in self.reader.rows():
            self.current_row = row

            try:
                self.import_row()
            except Exception as e:
                self.logger.error(e, row)
            else:
                self.logger.success(row)

    def number_to_datetime(self, number, datemode=0):
        date_args = xlrd.xldate_as_tuple(number, datemode)
        return datetime.datetime(*date_args)

    def string_to_datetime(self, datestring, format):
        datestring = datestring.strip()
        return datetime.datetime.strptime(datestring, format)

    def stripped_value_for(self, field_name):
        field_value = self.field_value_for(field_name)
        return unicode(field_value).strip()

    def value_to_datetime(self, value, format='%d/%m/%Y'):
        supported_formats = (
            '%d/%m/%Y',
            '%B %d, %Y',
            '%B %d,%Y',
        )
        try:
            value_as_number = float(value)
            return self.number_to_datetime(value_as_number)
        except ValueError:
            for supported_format in supported_formats:
                try:
                    return self.string_to_datetime(value, supported_format)
                except:
                    pass
            else:
                raise ValueError('A valid date format must be passed')
        return None


class SheetReader(object):
    def __init__(self, filename=None, name=None, encoding=None, content=None):
        book = xlrd.open_workbook(filename=filename, file_contents=content, encoding_override=encoding)
        if name:
            self.sheet = book.sheet_by_name(name)
        else:
            self.sheet = book.sheet_by_index(0)

    def assign_columns(self, columns):
        columns_by_numbers = SortedDict()
        for col_name, col_index in columns.items():
            columns_by_numbers[col_name] = self.normalized_column_index(col_index)

        self.columns = columns_by_numbers

    def auto_assign_columns(self, row_index=0, first_column=0, last_column=None):
        """
        @row_index: index of the header line.
        @first_column: index of the first column of the header.
        @last_column: index of the last column of the header. If None, it will load all columns of the header line.
        """
        self.columns = SortedDict()

        column_index = first_column
        while column_index <= last_column or last_column is None:
            try:
                header_name = self.sheet.cell_value(row_index - 1, column_index - 1)
            except IndexError:
                break
            self.columns[header_name] = self.normalized_column_index(column_index)
            column_index += 1

    def col_index_by_letters(self, letters):
        base = 26
        total = 0
        reversed_letters = tuple(reversed(letters))
        for index, _ in enumerate(reversed_letters):
            current_letter = reversed_letters[index]
            parser_index = self.letter_index(current_letter) + 1
            current_value = parser_index * (base ** index)
            total += current_value
        return total

    def letter_index(self, letter):
        letter_index = string.ascii_lowercase.find(letter.lower())
        return letter_index

    def normalized_column_index(self, col_index):
        if isinstance(col_index, str):
            return self.col_index_by_letters(col_index)
        else:
            return col_index

    def rows(self):
        if not hasattr(self, 'first_row'):
            raise NoSheetBoundariesError('You must define at least the first row')

        row_index = self.first_row
        while row_index <= self.last_row or self.last_row is None:
            fields = {}
            parser_row_index = row_index - 1
            for col_name, _ in self.columns.items():
                parser_col_index = self.columns[col_name] - 1
                try:
                    fields[col_name] = self.sheet.cell_value(parser_row_index, parser_col_index)
                except IndexError:
                    raise StopIteration()
            yield fields

            row_index += 1

    def set_boundaries(self, first_row=None, last_row=None):
        self.first_row = first_row
        self.last_row = last_row

    def name(self):
        return self.sheet.name

    def to_sheet_data(self):
        sheet_data = SheetData(self.sheet.name)
        for row in self.rows():
            cell_list = []
            for cell in row:
                # TODO: how to read span and style?
                cell_list.append(ExcelCell(cell))
            sheet_data.add_cell_list(cell_list)
        return sheet_data


class ExcelReader(object):
    def __init__(self, path, encoding=None):
        self.book = xlrd.open_workbook(path, encoding_override=encoding)
        self.path = path
        self.encoding = encoding

    # TODO: SheetReader only works with SheetRowOriented
    def get_excel_data(self, first_row=2, row_index=1, first_column=1):
        excel_data = ExcelData()
        for index in range(0, self.book.nsheets):
            sheet = self.book.sheet_by_index(index)
            reader = SheetReader(self.path, sheet.name, self.encoding)
            reader.set_boundaries(first_row=first_row)
            reader.auto_assign_columns(row_index, first_column)
            sheet_data = reader.to_sheet_data()
            excel_data.add_sheet(sheet_data)
        return excel_data


class SheetGenerator(object):
    def generate(self, excel_generator, sheet_data):
        pass


class SheetRowOriented(SheetGenerator):
    def generate(self, excel_generator, sheet_data):
        excel_generator._add_sheet(sheet_data.sheet_name)

        row = 0
        column = 0
        for cell_list in sheet_data.data():
            for cell in cell_list:  # cell can be a data or an ExcelCell
                if isinstance(cell, ExcelCell):
                    if not cell.ignored:
                        excel_generator._write_cell(row, column, cell)
                    column += cell.col_span
                else:
                    excel_generator._write_default_cell(row, column, cell)
                    column += 1
            row += 1
            column = 0
        return excel_generator._workbook


class SheetColumnOriented(SheetGenerator):
    def generate(self, excel_generator, sheet_data):
        excel_generator._add_sheet(sheet_data.sheet_name)

        row = 0
        column = 0
        for cell_list in sheet_data.data():
            for cell in cell_list:  # cell can be a data or an ExcelCell
                if isinstance(cell, ExcelCell):
                    if not cell.ignored:
                        excel_generator._write_cell(row, column, cell)
                    row += cell.row_span
                else:
                    excel_generator._write_default_cell(row, column, cell)
                    row += 1
            column += 1
            row = 0
        return excel_generator._workbook


class ExcelGenerator(object):
    "Create an excel by an ExcelData object."

    DATE_FORMAT = 'YYYY-MM-DD'
    DATETIME_FORMAT = 'YYYY-MM-DD hh:mm:ss'

    def __init__(self, date_format=DATE_FORMAT, datetime_format=DATETIME_FORMAT, encoding='utf-8'):
        self.date_format = date_format
        self.datetime_format = datetime_format

        if encoding:
            self._workbook = Workbook(encoding=encoding, style_compression=2)
        else:
            self._workbook = Workbook(style_compression=2)

        self._current_sheet = None

    def _add_sheet(self, name):
        self._current_sheet = self._workbook.add_sheet(name)

    def _write_default_cell(self, row_index, column_index, value):
        current_style = copy(DEFAULT_STYLE)
        if type(value) == datetime.date:
            current_style.num_format_str = self.date_format
        elif type(value) == datetime.datetime:
            current_style.num_format_str = self.datetime_format
        self._current_sheet.write(row_index, column_index, value, current_style)

    def _write_cell(self, row_index, column_index, cell):
        value = cell.data
        if isinstance(cell.style, str):
            current_style = easyxf(cell.style)
        elif isinstance(cell.style, ExcelCellStyle):
            current_style = easyxf(cell.style.get_style_str())
        else:
            current_style = copy(cell.style)
        if type(value) == datetime.date:
            current_style.num_format_str = self.date_format
        elif type(value) == datetime.datetime:
            current_style.num_format_str = self.datetime_format
        if cell.col_span == 1 and cell.row_span == 1:
            self._current_sheet.write(row_index, column_index, value, current_style)
        else:
            self._current_sheet.write_merge(row_index, row_index + cell.row_span - 1,
                                            column_index, column_index + cell.col_span - 1,
                                            value, current_style)

    def generate(self, excel_data):
        "return a Workbook"
        for sheet_data in excel_data.sheets():
            if sheet_data.orientation == 'column':
                SheetColumnOriented().generate(self, sheet_data)
            else:
                SheetRowOriented().generate(self, sheet_data)
        return self._workbook


class ExcelExporter(object):
    "Export an excel workbook."
    def save_to_file(self, workbook, filename):
        workbook.save(filename)


class Report(object):

    def __init__(self, name):
        self.name = name

    def get_sheet_data(self):
        pass

    def get_excel(self):
        excel_data = ExcelData()
        excel_data.add_sheet(self.get_sheet_data())
        excel_generator = ExcelGenerator()
        workbook = excel_generator.generate(excel_data)
        return workbook


class DefaultReport(Report):

    def get_list_of_base_models(self, *args, **kwargs):
        return []

    def get_header_groups(self):
        return None

    def get_header_columns(self):
        return []

    def populate_data_set(self, data, obj):
        pass

    def get_data_set(self, obj, header_columns):
        data = SortedDict()
        # header define the order of data and to do not leak an attribute
        for header in header_columns:
            if isinstance(header, ExcelCell):
                data[header.data] = ''
            else:
                data[header] = ''
        self.populate_data_set(data, obj)
        return data.values()

    def get_data(self, header_columns):
        data = []
        for obj in self.get_list_of_base_models():
            data.append(self.get_data_set(obj, header_columns))
        return data

    def get_sheet_data(self):
        sheet_data = SheetData(self.name)
        header_columns = self.get_header_columns()
        sheet_data.overwrite_data(self.get_data(header_columns))
        sheet_data.add_header(header_columns, append_in_the_beginning=True)
        if self.get_header_groups():
            sheet_data.add_cell_list(self.get_header_groups(), append_in_the_beginning=True)
        return sheet_data
