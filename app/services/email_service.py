"""
app/services/email_service.py
──────────────────────────────
Email delivery with two strategies:
  1. Resend SDK (recommended — handles deliverability, DKIM, bounce tracking)
  2. aiosmtplib SMTP fallback (for development / self-hosted setups)

The public interface is just ONE function: send_verification_email().
Swap the implementation without touching any router code.

How to choose:
  - Set RESEND_API_KEY in .env → Resend is used automatically.
  - Leave RESEND_API_KEY empty → SMTP fallback is used.
"""
import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

settings = get_settings()


# ── HTML email template ───────────────────────────────────────────────────────
def _build_verification_html(username: str, verify_url: str) -> tuple[str, str]:
    """
    Returns (plain_text, html_string) for the verification email.
    Keep HTML inline-styled — many email clients strip <style> tags.
    """
    plain = (
        f"Hi {username},\n\n"
        f"Welcome to NIZAM-RUS! Please verify your email by visiting:\n\n"
        f"{verify_url}\n\n"
        f"This link expires in 24 hours.\n\n"
        f"If you did not create an account, ignore this email."
    )
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f0f13;font-family:'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f13;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:#16161d;border:1px solid #2a2a3a;border-radius:12px;overflow:hidden;">
          <!-- Header -->
          <tr>
            <td style="background:#e05c5c;padding:28px 32px;">
              <h1 style="margin:0;color:#fff;font-size:22px;letter-spacing:0.05em;">
                NIZAM-RUS
              </h1>
              <p style="margin:4px 0 0;color:rgba(255,255,255,0.8);font-size:13px;">
                180-Day Russian Language Program
              </p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <p style="color:#e8e8f0;font-size:15px;margin:0 0 16px;">
                Hi <strong>{username}</strong>,
              </p>
              <p style="color:#9090a8;font-size:14px;line-height:1.7;margin:0 0 28px;">
                Your account has been created. Click the button below to verify your
                email address and activate your account.
              </p>
              <!-- CTA button -->
              <table cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td align="center">
                    <a href="{verify_url}"
                       style="display:inline-block;background:#e05c5c;color:#fff;
                              text-decoration:none;padding:13px 36px;border-radius:8px;
                              font-size:14px;font-weight:700;letter-spacing:0.03em;">
                      ✅ Verify My Email
                    </a>
                  </td>
                </tr>
              </table>
              <p style="color:#9090a8;font-size:12px;margin:28px 0 0;line-height:1.6;">
                Or copy this link into your browser:<br>
                <a href="{verify_url}" style="color:#e05c5c;word-break:break-all;">
                  {verify_url}
                </a>
              </p>
              <hr style="border:none;border-top:1px solid #2a2a3a;margin:28px 0;">
              <p style="color:#9090a8;font-size:11px;margin:0;">
                This link expires in <strong style="color:#e8e8f0;">24 hours</strong>.
                If you didn't create an account, you can safely ignore this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return plain, html


# ── Strategy 1: Resend SDK ────────────────────────────────────────────────────
async def _send_via_resend(to_email: str, subject: str, plain: str, html: str) -> None:
    """
    Send email using the Resend SDK.
    Resend handles DKIM, SPF, bounce tracking, and delivery receipts.

    Docs: https://resend.com/docs/send-with-python
    """
    import resend  # Imported lazily so missing dep only errors if this path is taken

    resend.api_key = settings.resend_api_key

    params: resend.Emails.SendParams = {
        "from": f"{settings.email_from_name} <{settings.email_from}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
        "text": plain,
    }

    # resend.Emails.send() is synchronous, run in a thread pool to avoid blocking
    await asyncio.get_event_loop().run_in_executor(None, resend.Emails.send, params)


# ── Strategy 2: SMTP fallback ─────────────────────────────────────────────────
async def _send_via_smtp(to_email: str, subject: str, plain: str, html: str) -> None:
    """
    Send email via SMTP using Python's stdlib smtplib.

    Note: smtplib is synchronous. We run it in a thread pool executor so it
    doesn't block the async event loop. For high throughput, replace with
    aiosmtplib (pip install aiosmtplib) — the API is nearly identical.
    """
    def _sync_send():
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.email_from_name} <{settings.email_from}>"
        msg["To"] = to_email

        # Attach plain first, then HTML — email clients prefer the last part
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            if settings.smtp_tls:
                server.starttls(context=context)
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.email_from, to_email, msg.as_string())

    # Run blocking SMTP in a thread to avoid freezing FastAPI's async loop
    await asyncio.get_event_loop().run_in_executor(None, _sync_send)


# ── Public interface ──────────────────────────────────────────────────────────
async def send_verification_email(
    to_email: str,
    username: str,
    token: str,
    base_url: str = "http://localhost:8000",
) -> None:
    """
    Send an email-verification message to a newly registered user.

    Args:
        to_email:  Recipient's email address.
        username:  Used in the greeting line.
        token:     The secure random token stored in the DB.
        base_url:  Your API's public URL. The verification link points here.

    The frontend can also handle verification if you prefer:
        verify_url = f"{settings.frontend_origin}/verify?token={token}"
    """
    verify_url = f"{base_url}/api/auth/verify-email?token={token}"
    subject = "Verify your NIZAM-RUS account"
    plain, html = _build_verification_html(username, verify_url)

    if settings.resend_api_key:
        await _send_via_resend(to_email, subject, plain, html)
    else:
        # Development fallback — configure SMTP_ vars in .env
        await _send_via_smtp(to_email, subject, plain, html)
