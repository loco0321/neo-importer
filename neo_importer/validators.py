# -*- coding: utf-8 -*-
import six
from django.core.exceptions import ValidationError
from django.core.validators import BaseValidator
from django.contrib.auth.models import User
from datetime import datetime, date
from decimal import Decimal
import time

# from lib.utils import validate_date_from_file


class FieldValidator(object):
    def validate(self, key, value): pass


class RequiredValidator(BaseValidator):

    def __init__(self, required):
       self.required = required

    def __call__(self, value):
        if self.required:
            if isinstance(value, str):
                value = value.strip()
            if value is None or value == '':
                raise ValidationError('Is required')


class DateValidator(BaseValidator):

    def __init__(self, date_formats):
        if not isinstance(date_formats, (list, tuple)):
            date_formats = [date_formats]

        self.date_formats = date_formats

    def __call__(self, value):
        if value:
            value = value.lower()
            if value in ('na', 'n/a'):
                return

            for d_format in self.date_formats:
                try:
                    datetime.strptime(value, d_format)
                    return
                except ValueError:
                    pass
            try:
                import xlrd
                year, month, day, h, m, s = xlrd.xldate_as_tuple(int(value), 0)
                return
            except:
                pass
            actual_date = datetime.today()
            raise ValidationError(
                u'Invalid format for date. Valid formats are ({0})'.format(
                    u' - '.join([actual_date.strftime(x) for x in self.date_formats])
                )
            )


class ChoicesValidator(BaseValidator):

    def __init__(self, choices, ignore_case=False, allow_empty_value=False):
        self.ignore_case = ignore_case
        if ignore_case:
            if six.PY2:
                self.choices = map(lambda x: str(x, 'utf-8').upper(), choices)

            else:
                self.choices = map(lambda x: str(x).upper(), choices)

            self.choices = list(self.choices)

        else:
            self.choices = choices
        if allow_empty_value:
            self.choices.append("")

    def __call__(self, value):
        if self.ignore_case:
            if six.PY2:
                value = str(value, 'utf-8').upper()

            else:
                value = str(value).upper()

        if not (value in self.choices):
            if "" in self.choices:
                self.choices.remove("")
                raise ValidationError(
                    u'Value "{0}" is not a valid option. valid option are ({1}) or empty'.format(
                        value,
                        u', '.join(self.choices)
                    )
                )
            else:
                raise ValidationError(
                    u'Value "{0}" is not a valid option. valid option are ({1})'.format(
                        value,
                        u', '.join(self.choices)
                    )
                )


class ExactLenghtValidator(BaseValidator):

    def __init__(self, max_length):
       self.max_length = max_length

    def __call__(self, value):
        if value and len(str(value, 'utf-8')) != self.max_length:
            raise ValidationError(
                'Ensure this value is equal to {0} characters (it has {1})'.format(
                    self.max_length,
                    value,
                )
            )


def validate_integer(value):
    try:
        if value:
            int(value)
    except (ValueError, TypeError) as e:
        raise ValidationError('This field requires an integer number')


def validate_float(value):
    try:
        if value:
            float(value)
    except (ValueError, TypeError) as e:
        raise ValidationError('This field requires a decimal number')



class LimitLengthValidator(BaseValidator):
    def __init__(self, max_length):
        self.max_length = max_length

    def __call__(self, value):
        if value and len(value) > self.max_length:
            raise ValidationError(
                'Ensure this value is less or equal than {0} characters (it has {1})'.format(
                    self.max_length,
                    value,
                )
            )


def validate_float_with_commas(value):
    try:
        if value:
            float(value)
    except (ValueError, TypeError) as e:
        try:
            if value:
                float(str(value).replace(",", "."))
        except (ValueError, TypeError) as e:
            raise ValidationError('This field requires a decimal number format')


class ValidateUserPerms(BaseValidator):
    def __init__(self, user, perm):
        self.user = user
        self.perm = perm

    def __call__(self, value):
        try:
            if (self.user and not self.user.has_perms(self.perm)) or not self.user:
                raise ValidationError("You don't have permissions to modify this field")
        except:
            raise ValidationError("You don't have permissions to modify this field")
