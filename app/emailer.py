from flask import current_app
import smtplib  
import email.utils as email_utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app import create_celery_app
celery = create_celery_app()


def send_email(to, subject, html_body):
    """Wrap async email sender"""
    _send_email.apply_async(args=[to, subject, html_body])


@celery.task(bind=True, max_retries=2)
def _send_email(self, to, subject, html_body):

    # We intentionally commented out this code - we used it to prevent emails in development from going to non-Staffjoy emails.
    """
    if current_app.config.get("ENV") != "prod":
        allowed_domains = ["@staffjoy.com", "@7bridg.es"]
        ok = False
        for d in allowed_domains:
            if to[-len(d):].lower() == d:
                ok = True

        if not ok:
            current_app.logger.info(
                "Intercepted email to %s and prevented sending due to environment rules."
                % to)
            return
    """

    if to in current_app.config.get("EMAIL_BLACKLIST") or (
            to.startswith("demo+") and to.endswith("@7bridg.es")):
        current_app.logger.debug(
            "Not sending email to %s becuase it is blacklisted" % to)
        return

    current_app.logger.info("Sending an email to %s - subject '%s' - body %s" %
                            (to, subject, html_body))

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = email_utils.formataddr(("Staffjoy", current_app.config.get("FROM_EMAIL")))
    msg['To'] = to

    # Record the MIME types of both parts - text/plain and text/html.
    part2 = MIMEText(html_body, 'html')

    # Attach parts into message container.
    # According to RFC 2046, the last part of a multipart message, in this case
    # the HTML message, is best and preferred.
    msg.attach(part2)

    try:

        server = smtplib.SMTP(current_app.config.get("SMTP_HOST"), 587)
        server.ehlo()
        server.starttls()
        #stmplib docs recommend calling ehlo() before & after starttls()
        server.ehlo()
        server.login(current_app.config.get("SMTP_USER"), current_app.config.get("SMTP_PASSWORD"))
        server.sendmail(current_app.config.get("FROM_EMAIL"), to, msg.as_string())
        server.close()
    except Exception as e:
        current_app.logger.exception(
            'An smtp error to email %s occurred: %s - %s' %
            (to, e.__class__, e))
        raise self.retry(exc=e)
