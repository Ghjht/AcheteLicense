import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from flask import current_app, render_template
from pathlib import Path


def send_order_email(order, pdf_path=None):
    app = current_app
    mail_server = app.config['MAIL_SERVER']
    mail_port = app.config['MAIL_PORT']
    mail_use_tls = app.config['MAIL_USE_TLS']
    mail_username = app.config['MAIL_USERNAME']
    mail_password = app.config['MAIL_PASSWORD']
    mail_sender = app.config['MAIL_DEFAULT_SENDER']

    if not mail_username or not mail_password:
        app.logger.warning('Email not configured. Skipping email send.')
        return False

    recipient = order.customer_email
    if not recipient:
        app.logger.warning(f'No email for order #{order.id}')
        return False

    subject = f'Your AcheteLicense Order #{order.id} - Confirmed!'

    html_body = render_template('email/order_confirmation.html', order=order)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = mail_sender
    msg['To'] = recipient

    part = MIMEText(html_body, 'html')
    msg.attach(part)

    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, 'rb') as f:
            attachment = MIMEBase('application', 'octet-stream')
            attachment.set_payload(f.read())
            encoders.encode_base64(attachment)
            attachment.add_header(
                'Content-Disposition',
                f'attachment; filename=invoice_{order.id}.pdf'
            )
            msg.attach(attachment)

    try:
        with smtplib.SMTP(mail_server, mail_port) as server:
            if mail_use_tls:
                server.starttls()
            if mail_username and mail_password:
                server.login(mail_username, mail_password)
            server.send_message(msg)
        app.logger.info(f'Order confirmation email sent to {recipient}')
        return True
    except Exception as e:
        app.logger.error(f'Failed to send email: {e}')
        return False
