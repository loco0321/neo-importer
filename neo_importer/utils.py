import six


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
        'grouped_fields': results.grouped_fields,
        'grouped_fields_labels': results.grouped_fields_labels,
        'ignored_elements': results.ignored_elements,
        'single_elements': results.single_elements,
    }
    return results_format
