import os
import logging
import datetime
import difflib
import tempfile
import codecs

from camelot.core.resources import resource_filename
from camelot.test import ModelThreadTestCase
from camelot.core.templates import environment

import vfinance
from vfinance.model.financial.notification.environment import TemplateLanguage
from vfinance.admin.jinja2_filters import datetime as format_datetime

logger = logging.getLogger(__name__)
REFERENCE_DATETIME = datetime.datetime(2012, 8, 10, 1, 0, 0)


class TestDocument(ModelThreadTestCase):

    def verify_document(self, template, context, reference_filename=None, string_replacements=[]):
        """:param string_replacements: string of tuples like [(find_string, replace_string),]
                                       this is to have consistency in dynamic content such as today's date etc
        """
        if not reference_filename:
            reference_filename = template

        with TemplateLanguage('nl'):
            # template = environment.get_template( template )
            with codecs.open(self._get_template_filepath(template), encoding='utf-8', mode='rb') as template_file:
                template = environment.from_string(template_file.read())
                generated_content = template.render(context)

        # replace strings that are always going to differ from the reference doc
        if 'now' in context:
            string_replacements.insert(0, (format_datetime(context['now']),
                                           format_datetime(REFERENCE_DATETIME)))
        for find, replace in string_replacements:
            logger.debug(u'Replacing {0} with {1}'.format(find, replace))
            generated_content = generated_content.replace(find, replace)

        # generate the reference doc to visually inspect
        self._generate_reference_doc(reference_filename, generated_content)
        # get reference content
        with codecs.open(self._get_reference_filepath(reference_filename), encoding='utf-8', mode='rb') as reference_file:
            reference_content = reference_file.read()

        diff = False
        for line in difflib.context_diff(generated_content.split('\n'), reference_content.split('\n')):
            logger.debug(line)
            diff = True
        self.assertFalse(diff)

    def _generate_reference_doc(self, reference_filename, generated_content):
        filename = os.path.join(tempfile.gettempdir(), reference_filename)
        if not os.path.isdir(os.path.dirname(filename)):
            os.mkdir(os.path.dirname(filename))
        with open(filename, 'w+b') as tmp:
            tmp.write(generated_content.encode('utf-8'))
            logger.debug('Generated content to file: {0}'.format(tmp.name))

    def _get_template_filepath(self, template_filename):
        return resource_filename(vfinance.__name__,
                                 '{0}/{1}/{2}'.format('art',
                                                      'templates',
                                                      template_filename))

    def _get_reference_filepath(self, reference_filename):
        return resource_filename(vfinance.__name__,
                                 '{0}/{1}/{2}/{3}'.format('art',
                                                          'templates',
                                                          'reference_documents',
                                                          reference_filename))
