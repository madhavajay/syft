from typing import Union

from pydantic import BaseModel, EmailStr, NameEmail

from .constants import FROM_EMAIl


class SendEmailRequest(BaseModel):
    to: Union[EmailStr, NameEmail]
    subject: str
    html: str

    def json_for_request(self):
        return {
            "personalizations": [{"to": [{"email": self.to}]}],
            "from": {"email": FROM_EMAIl},
            "subject": self.subject,
            "content": [{"type": "text/html", "value": self.html}],
        }
