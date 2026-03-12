"""
Serviço de envio de email para alertas MSM_Pro.

Usa smtplib com as configurações de SMTP definidas em settings.
Se SMTP não estiver configurado, registra o email no log sem falhar.
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
    # Verifica se SMTP está configurado
    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_pass:
        logger.warning(
            "SMTP não configurado — email não enviado. "
            "Destinatário: %s | Assunto: %s | Mensagem: %s",
            to,
            subject,
            body,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
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

        logger.info("Email enviado para %s: %s", to, subject)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Falha de autenticação SMTP ao enviar para %s", to)
    except smtplib.SMTPConnectError as exc:
        logger.error("Erro de conexão SMTP: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro inesperado ao enviar email para %s: %s", to, exc)

    return False
