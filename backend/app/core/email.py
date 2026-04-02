"""
Serviço de envio de email para alertas e relatórios MSM_Pro.

Usa smtplib com as configurações de SMTP definidas em settings.
Compatível com Gmail (smtp.gmail.com:587 + STARTTLS + App Password).

Se SMTP não estiver configurado, registra o email no log sem falhar.

Variáveis de ambiente necessárias:
  SMTP_HOST = smtp.gmail.com
  SMTP_PORT = 587
  SMTP_USER = seu@gmail.com
  SMTP_PASS = xxxx xxxx xxxx xxxx  (Gmail App Password)
  SMTP_FROM = MSM_Pro <seu@gmail.com>  (opcional — usa SMTP_USER se omitido)
  SMTP_TO   = maikeo@msmrp.com         (destinatário padrão dos relatórios)
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


# --- Template HTML básico ---

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{subject}</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #fff;
                 border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,.1); }}
    .header {{ background: #2563eb; color: #fff; padding: 24px 32px; }}
    .header h1 {{ margin: 0; font-size: 20px; }}
    .body {{ padding: 32px; color: #333; line-height: 1.6; }}
    .footer {{ background: #f0f0f0; padding: 16px 32px; font-size: 12px; color: #888;
               text-align: center; }}
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px;
              background: #fef3c7; color: #92400e; font-weight: bold; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>MSM_Pro — Alerta de Venda</h1>
    </div>
    <div class="body">
      <p>{body_html}</p>
    </div>
    <div class="footer">
      Este email foi gerado automaticamente pelo sistema MSM_Pro.<br/>
      Acesse o <a href="{frontend_url}">dashboard</a> para mais detalhes.
    </div>
  </div>
</body>
</html>
"""


def _build_html(subject: str, body: str) -> str:
    """Monta o HTML do email substituindo quebras de linha por <br>."""
    body_html = body.replace("\n", "<br/>")
    return _HTML_TEMPLATE.format(
        subject=subject,
        body_html=body_html,
        frontend_url=settings.frontend_url,
    )


def _get_sender() -> str:
    """Retorna o remetente configurado, com fallback para smtp_user."""
    return settings.smtp_from or settings.smtp_user or ""


def is_smtp_configured() -> bool:
    """Verifica se SMTP está configurado com os campos obrigatórios."""
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_pass)


def send_html_email(to: str, subject: str, html: str) -> bool:
    """
    Envia email com HTML arbitrário (sem wrapper do template de alertas).
    Usado pelo Daily Intel Report, weekly digest e outros transacionais.

    Retorna True se enviado com sucesso, False caso contrário.
    Se SMTP não estiver configurado, apenas loga e retorna False sem falhar.
    """
    if not is_smtp_configured():
        logger.warning(
            "SMTP não configurado — email não enviado. "
            "Configure SMTP_HOST, SMTP_USER e SMTP_PASS nas variáveis de ambiente. "
            "Destinatário: %s | Assunto: %s",
            to,
            subject,
        )
        return False

    sender = _get_sender()

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to

        part_html = MIMEText(html, "html", "utf-8")
        msg.attach(part_html)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_user, [to], msg.as_string())

        logger.info("Email HTML enviado para %s: %s", to, subject)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Falha de autenticação SMTP ao enviar para %s. "
            "Verifique SMTP_USER e SMTP_PASS (Gmail: use App Password, não a senha normal).",
            to,
        )
    except smtplib.SMTPConnectError as exc:
        logger.error("Erro de conexão SMTP (%s:%d): %s", settings.smtp_host, settings.smtp_port, exc)
    except smtplib.SMTPRecipientsRefused as exc:
        logger.error("Destinatário recusado pelo servidor SMTP: %s — %s", to, exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro inesperado ao enviar email HTML para %s: %s", to, exc)

    return False


def send_alert_email(to: str, subject: str, body: str) -> bool:
    """
    Envia email de alerta para o destinatário.

    Parâmetros:
        to      - endereço do destinatário
        subject - assunto do email
        body    - corpo em texto simples (será convertido para HTML)

    Retorna True se enviado com sucesso, False caso contrário.
    Se SMTP não estiver configurado, apenas loga e retorna False sem falhar.
    """
    if not is_smtp_configured():
        logger.warning(
            "SMTP não configurado — email não enviado. "
            "Destinatário: %s | Assunto: %s | Mensagem: %s",
            to,
            subject,
            body,
        )
        return False

    sender = _get_sender()

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to

        # Parte texto simples (fallback)
        part_text = MIMEText(body, "plain", "utf-8")
        # Parte HTML
        part_html = MIMEText(_build_html(subject, body), "html", "utf-8")

        msg.attach(part_text)
        msg.attach(part_html)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(settings.smtp_user, [to], msg.as_string())

        logger.info("Email de alerta enviado para %s: %s", to, subject)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Falha de autenticação SMTP ao enviar para %s. "
            "Gmail: use App Password (não a senha normal).",
            to,
        )
    except smtplib.SMTPConnectError as exc:
        logger.error("Erro de conexão SMTP (%s:%d): %s", settings.smtp_host, settings.smtp_port, exc)
    except smtplib.SMTPRecipientsRefused as exc:
        logger.error("Destinatário recusado pelo servidor SMTP: %s — %s", to, exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro inesperado ao enviar email para %s: %s", to, exc)

    return False
