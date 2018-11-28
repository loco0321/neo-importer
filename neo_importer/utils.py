import six


def handle_string(value):
    if six.PY3:
        return str(value)
    else:
        return six.text_type(value)
