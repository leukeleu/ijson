# -*- coding:utf-8 -*-
from __future__ import unicode_literals
import unittest
from io import BytesIO
from decimal import Decimal
import threading
from importlib import import_module

from ijson import common
from ijson.backends.python import basic_parse
from ijson.compat import IS_PY2


JSON = b'''
{
  "docs": [
    {
      "string": "\\u0441\\u0442\\u0440\\u043e\\u043a\\u0430 - \xd1\x82\xd0\xb5\xd1\x81\xd1\x82",
      "null": null,
      "boolean": false,
      "integer": 0,
      "double": 0.5,
      "exponent": 1.0e+2,
      "long": 10000000000
    },
    {
      "meta": [[1], {}]
    },
    {
      "meta": {"key": "value"}
    },
    {
      "meta": null
    }
  ]
}
'''
SCALAR_JSON = b'0'
EMPTY_JSON = b''
INVALID_JSON = b'{"key": "value",}'
INCOMPLETE_JSON = b'"test'
STRINGS_JSON = br'''
{
    "str1": "",
    "str2": "\"",
    "str3": "\\",
    "str4": "\\\\"
}
'''

class Parse(object):
    '''
    Base class for parsing tests that is used to create test cases for each
    available backends.
    '''
    def test_basic_parse(self):
        events = list(self.backend.basic_parse(BytesIO(JSON)))
        reference = [
            ('start_map', None),
                ('map_key', 'docs'),
                ('start_array', None),
                    ('start_map', None),
                        ('map_key', 'string'),
                        ('string', 'строка - тест'),
                        ('map_key', 'null'),
                        ('null', None),
                        ('map_key', 'boolean'),
                        ('boolean', False),
                        ('map_key', 'integer'),
                        ('number', 0),
                        ('map_key', 'double'),
                        ('number', Decimal('0.5')),
                        ('map_key', 'exponent'),
                        ('number', Decimal('100')),
                        ('map_key', 'long'),
                        ('number', 10000000000),
                    ('end_map', None),
                    ('start_map', None),
                        ('map_key', 'meta'),
                        ('start_array', None),
                            ('start_array', None),
                                ('number', 1),
                            ('end_array', None),
                            ('start_map', None),
                            ('end_map', None),
                        ('end_array', None),
                    ('end_map', None),
                    ('start_map', None),
                        ('map_key', 'meta'),
                        ('start_map', None),
                            ('map_key', 'key'),
                            ('string', 'value'),
                        ('end_map', None),
                    ('end_map', None),
                    ('start_map', None),
                        ('map_key', 'meta'),
                        ('null', None),
                    ('end_map', None),
                ('end_array', None),
            ('end_map', None),
        ]
        for e, r in zip(events, reference):
            self.assertEqual(e, r)

    def test_basic_parse_threaded(self):
        thread = threading.Thread(target=self.test_basic_parse)
        thread.start()
        thread.join()

    def test_scalar(self):
        events = list(self.backend.basic_parse(BytesIO(SCALAR_JSON)))
        self.assertEqual(events, [('number', 0)])

    def test_strings(self):
        events = list(self.backend.basic_parse(BytesIO(STRINGS_JSON)))
        strings = [value for event, value in events if event == 'string']
        self.assertEqual(strings, ['', '"', '\\', '\\\\'])

    def test_empty(self):
        self.assertRaises(
            common.IncompleteJSONError,
            lambda: list(self.backend.basic_parse(BytesIO(EMPTY_JSON))),
        )

    def test_incomplete(self):
        self.assertRaises(
            common.IncompleteJSONError,
            lambda: list(self.backend.basic_parse(BytesIO(INCOMPLETE_JSON))),
        )

    def test_invalid(self):
        self.assertRaises(
            common.JSONError,
            lambda: list(self.backend.basic_parse(BytesIO(INVALID_JSON))),
        )

    def test_utf8_split(self):
        buf_size = JSON.index(b'\xd1') + 1
        try:
            events = list(self.backend.basic_parse(BytesIO(JSON), buf_size=buf_size))
        except UnicodeDecodeError:
            self.fail('UnicodeDecodeError raised')

    def test_lazy(self):
        # shouldn't fail since iterator is not exhausted
        self.backend.basic_parse(BytesIO(INVALID_JSON))
        self.assertTrue(True)

    def test_exponent(self):
        """
        Test the parsing of exponents; some valid exponents are:
        - with 'e': 1e2
        - with 'E': 1E2
        - with dot: 1.0e2

        Also see diagram at json.org
        """
        def parse_decimal(value):
            events = list(self.backend.basic_parse(BytesIO(value)))
            self.assertEqual(events, [('number', Decimal(value))])

        parse_decimal(b'1.0e2')
        parse_decimal(b'1e2')
        parse_decimal(b'1E2')
        parse_decimal(b'1.0E2')
        parse_decimal(b'-1e2')
        parse_decimal(b'1e+2')
        parse_decimal(b'1e-2')

# Generating real TestCase classes for each importable backend
for name in ['python', 'yajl', 'yajl2']:
    try:
        classname = '%sParse' % name.capitalize()
        if IS_PY2:
            classname = classname.encode('ascii')
        locals()[classname] = type(
            classname,
            (unittest.TestCase, Parse),
            {'backend': import_module('ijson.backends.%s' % name)},
        )
    except ImportError:
        pass

class Common(unittest.TestCase):
    '''
    Backend independent tests. They all use basic_parse imported explicitly from
    the python backend to generate parsing events.
    '''
    def test_object_builder(self):
        builder = common.ObjectBuilder()
        for event, value in basic_parse(BytesIO(JSON)):
            builder.event(event, value)
        self.assertEqual(builder.value, {
            'docs': [
                {
                   'string': 'строка - тест',
                   'null': None,
                   'boolean': False,
                   'integer': 0,
                   'double': Decimal('0.5'),
                   'exponent': Decimal('100'),
                   'long': 10000000000,
                },
                {
                    'meta': [[1], {}],
                },
                {
                    'meta': {'key': 'value'},
                },
                {
                    'meta': None,
                },
            ],
        })

    def test_scalar_builder(self):
        builder = common.ObjectBuilder()
        for event, value in basic_parse(BytesIO(SCALAR_JSON)):
            builder.event(event, value)
        self.assertEqual(builder.value, 0)

    def test_parse(self):
        events = common.parse(basic_parse(BytesIO(JSON)))
        events = [value
            for prefix, event, value in events
            if prefix == 'docs.item.meta.item.item'
        ]
        self.assertEqual(events, [1])

    def test_items(self):
        events = basic_parse(BytesIO(JSON))
        meta = list(common.items(common.parse(events), 'docs.item.meta'))
        self.assertEqual(meta, [
            [[1], {}],
            {'key': 'value'},
            None,
        ])


if __name__ == '__main__':
    unittest.main()
