import logging

from camelot.core.qt import QtGui
from camelot.core.utils import ugettext as _
from camelot.admin.action import Action
from camelot.view.model_thread import post
from camelot.view.art import Icon
from camelot.view.controls.progress_dialog import ProgressDialog
from camelot.view.controls.user_translatable_label import UserTranslatableLabel
from camelot.view.controls.editors.richtexteditor import RichTextEditor

logger = logging.getLogger('vfinance.admin.form_action')

class SendEmailProgressDialog(ProgressDialog):

    def __init__(self, name, icon=Icon('tango/32x32/actions/appointment-new.png')):
        super(SendEmailProgressDialog, self).__init__(name=name, icon=icon)

    def email_result(self, dlg):
        self.close()
        if dlg:
            dlg.close()

class EmailDialog(QtGui.QDialog):
    
    def __init__(self, parent=None, html=None, headers={}):
        super(EmailDialog, self).__init__(parent=parent)
        self.setWindowTitle(_('Send E-mail'))

        self.headers = headers

        layout = QtGui.QGridLayout()

        self.field_names = ['From', 'To', 'Cc', 'Bcc', 'Subject']
        for field_name in self.field_names:
            field_label = UserTranslatableLabel(_(field_name), parent=self)
            field = QtGui.QLineEdit(parent=self)
            field.setObjectName('mail_' + field_name.lower())
            if field_name in headers and headers[field_name]:
                field.setText(headers[field_name])
            layout.addWidget(field_label, self.field_names.index(field_name), 0)
            layout.addWidget(field, self.field_names.index(field_name), 1)

        body = RichTextEditor(parent=self)
        body.setObjectName('mail_body')
        if html:
            body.set_value(html)
        layout.addWidget(body, len(self.field_names), 0, 3, 2)

        button_layout = QtGui.QHBoxLayout()
        button_layout.addStretch(1)
        cancel_button = QtGui.QPushButton(_("Cancel"))
        cancel_button.clicked.connect(self.signal_close)
        button_layout.addWidget(cancel_button)
        send_button = QtGui.QPushButton(_("Send"))
        send_button.clicked.connect(self.signal_send)
        button_layout.addWidget(send_button)

        layout.addLayout(button_layout, len(self.field_names)+3, 1)

        self.setLayout(layout)

    def signal_send(self):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart('alternative')

        for k,v in self.headers.items():
            msg[k] = v
        for field_name in self.field_names:
            msg[field_name] = unicode(self.findChild(QtGui.QWidget, 'mail_' + field_name.lower()).text())

        text = unicode(self.findChild(QtGui.QWidget, 'mail_body').textedit.toPlainText())
        html = unicode(self.findChild(QtGui.QWidget, 'mail_body').get_value())
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))

        def _send():
            import smtplib

            s = smtplib.SMTP('localhost')
            s.sendmail(msg['From'], msg['To'], msg.as_string())
            s.quit()
            return self

        progress = SendEmailProgressDialog(_('Sending Email'))
        post( _send, progress.email_result, exception=progress.exception )
        progress.exec_()

    def signal_close(self):
        self.close()

class ComposeEmailProgressDialog(ProgressDialog):

    def __init__(self, name, icon=Icon('tango/32x32/actions/appointment-new.png')):
        super(ComposeEmailProgressDialog, self).__init__(name=name, icon=icon)
        self.html_document = None

    def email_result(self, html_and_headers):
        self.close()

        html, headers = html_and_headers

        mail_dialog = EmailDialog(parent=self, html=html, headers=headers)
        mail_dialog.exec_()

        #open_html_in_print_preview_from_gui_thread(
        #    html, self.html_document,
        #    self.page_size, self.page_orientation
        #)


class EmailHtmlFormAction( Action ):
    """Create an action for a form that pops up an email message.
Overwrite the html function to customize the html that should be shown::

  class EmailMovieAction(EmailHtmlFormAction):

    def html(self, movie):
      html = '<h1>' + movie.title + '</h1>'
      html += movie.description
    return html

  class Movie(Entity):
    title = schema.Column(Unicode(60), nullable=False)
    description = schema.Column(camelot.types.RichText)

    class Admin(EntityAdmin):
      list_display = ['title', 'description']
      form_actions = [PrintMovieAction('summary')]

will put a print button on the form :

.. image:: /_static/formaction/print_html_form_action.png

    """

    icon=Icon('tango/16x16/actions/document-print.png')

    def email_headers(self, obj):
        """Overwrite this function to generate custom email headers to be printed
:param obj: the object that is displayed in the form
:return: a dictionary containing the email headers to be used (see RFC 2822 http://tools.ietf.org/html/rfc2822.html for possible keys)."""
        return {}

    def html(self, obj):
        """Overwrite this function to generate custom html to be printed
:param obj: the object that is displayed in the form
:return: a string with the html that should be displayed in a print preview window"""
        return '<h1>' + unicode( obj ) + '<h1>'

    def run( self, entity_getter ):
        """When the run method is called, a progress dialog will apear while
the model function is executed.

:param entity_getter: a function that when called returns the object currently in the form.
        
        """
        progress = ComposeEmailProgressDialog(self._name)

        def _request():
            o = entity_getter()
            return self.html(o), self.email_headers(o)

        post( _request, progress.email_result, exception = progress.exception )
        progress.exec_()

