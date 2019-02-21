import importlib
import re

import six

ALPHABETIC = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

FACTOR = 26

DELAY = 1

REGEX_CELL = '(?P<col>[a-zA-Z]+)(?P<row>[1-9]\d*)'


def handle_string(value):
    if six.PY3:
        return str(value)
    else:
        return six.text_type(value)


def format_results(results):
    if isinstance(results, list):
        results_format = []
        for result in results:
            results_format.append({
                'columns_mapping': result.columns_mapping,
                'columns_to_group': result.columns_to_group,
                'data': result.data,
                'data_summary': get_data_summary(result.data),
                'grouped_fields': result.grouped_fields,
                'grouped_fields_labels': result.grouped_fields_labels,
                'ignored_elements': result.ignored_elements,
                'single_elements': result.single_elements,
                'file_upload_history': result.file_upload_history
            })
        return results_format
    results_format = {
        'columns_mapping': results.columns_mapping,
        'columns_to_group': results.columns_to_group,
        'data': results.data,
        'data_summary': get_data_summary(results.data),
        'grouped_fields': results.grouped_fields,
        'grouped_fields_labels': results.grouped_fields_labels,
        'ignored_elements': results.ignored_elements,
        'single_elements': results.single_elements,
    }
    return results_format


def get_data_summary(data):
    data_summary = data.copy()
    data_summary['errors'] = len(data.get('errors', []))
    data_summary['infos'] = len(data.get('infos', []))
    data_summary['warnings'] = len(data.get('warnings', []))
    return data_summary


def convert_letter_to_number(letter):
    try:
        return ALPHABETIC.index(letter.upper())
    except ValueError as ve:
        raise ValueError('{0} [{1}] on ALPHABETIC = {2}'.format(ve, letter.upper(), ALPHABETIC))


def convert_list_number_to_decimal_integer(list_number):
    list_number_reversed = list(reversed(list_number))
    final_number = 0
    for number, exp in zip(list_number_reversed, range(len(list_number_reversed))):
        final_number += (number + DELAY) * (FACTOR ** exp)
    return final_number - DELAY


def convert_alphabetic_column_to_number(alphabetic_column):
    number_list = list(map(convert_letter_to_number, list(alphabetic_column)))
    return convert_list_number_to_decimal_integer(number_list)


def convert_alphabetic_cell_to_number(alphabetic_cell):
    match = re.findall(REGEX_CELL, alphabetic_cell)
    if not match:
        raise ValueError('Not valid cell {0}'.format(alphabetic_cell))
    alphabetic_column, row = match[0]
    return {
        'row': int(row) - 1,
        'col': convert_alphabetic_column_to_number(alphabetic_column),
    }


def get_cell_mapping(cell_mapping):
    new_cell_mapping = cell_mapping.copy()
    for field_name, config in cell_mapping.items():
        cell = config['cell']
        if isinstance(cell, str):
            new_cell_mapping[field_name]['cell'] = convert_alphabetic_cell_to_number(config['cell'])
        elif isinstance(cell, list) or isinstance(cell, tuple):
            new_cell_mapping[field_name]['cell'] = {'row': cell[0], 'col': cell[1]}
        elif isinstance(cell, dict):
            new_cell_mapping[field_name]['cell'] = {'row': cell['row'], 'col': cell['col']}
        else:
            raise ValueError('Cell "' + str(cell) + '" is no valid. The valid config are {"row":x, "col":y}, [x,y] and AB11')
    return new_cell_mapping


def custom_import(import_path):
    modules = [i.strip() for i in import_path.split('.')]
    try:
        return importlib.import_module(import_path)
    except ModuleNotFoundError as e:
        if len(modules) > 1:
            path_body = '.'.join(modules[:-1])
            module_body = importlib.import_module(path_body)
            return getattr(module_body, modules[-1])
        raise e


def get_path_import_from_class(python_class):
    return '{}.{}'.format(python_class.__module__, python_class.__name__)
