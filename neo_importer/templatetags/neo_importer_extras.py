# -*- coding: utf-8 -*-
from django import template
from django.template.loader import render_to_string

from neo_importer import importer_site

register = template.Library()


@register.filter
def get_importer(user, importer_key):
    importer = importer_site.get_importer(importer_key)
    if importer is None:
        raise Exception('Importer key "{0}" dont exist'.format(importer_key))

    if user.has_perm(importer.get_permission_code()):
        return importer

    else:
        return None


@register.simple_tag
def generate_importer_link( user, importer_key):
    importer = get_importer(user, importer_key)
    template_html = ''
    if importer:
        template_html = render_to_string(
            importer.get_importer_menu_template(),
            {
                'importer': importer
            }
        )

    return template_html

@register.filter
def get_item(dictionary, key):
    target = dictionary.get(key, '')
    if isinstance(target, list):
        target = ', '.join(target)
    return target


@register.filter
def prepare_list_elements(result, group):
    return result.prepare_list_elements(group)


@register.filter
def get_columns_to_group_values(result, group):
    return result.get_columns_to_group_values(group)


@register.filter
def get_error(msgs, key):
    lines = []
    error = ''
    value = None
    for msg in msgs:
        if msg.get('field') == key:
            lines.append(str(msg.get('line')))
            error = msg.get('msg')
            value = msg.get('value')
    if error:
        try:
            if len(lines) == 1:
                title = 'Error in line: {0}'.format(lines[0])
            else:
                title = 'Error in lines: {0}'.format(', '.join(lines))

            return {'title': title,
                    'msg': error,
                    'value': value}
        except Exception as e:
            return {
                'title': 'Unknown Error',
                'msg': str(e)
            }


