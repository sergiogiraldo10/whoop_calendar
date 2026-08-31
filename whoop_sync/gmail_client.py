import base64

import requests

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


def send_email(access_token: str, to: str, subject: str, body_text: str) -> None:
    message = f"To: {to}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n{body_text}"
    raw = base64.urlsafe_b64encode(message.encode("utf-8")).decode("ascii").rstrip("=")

    res = requests.post(
        f"{GMAIL_API_BASE}/users/me/messages/send",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"raw": raw},
    )
    res.raise_for_status()
