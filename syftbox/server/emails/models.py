from typing import Union

from pydantic import BaseModel, EmailStr, NameEmail

from .constants import FROM_EMAIl


class SendEmailRequest(BaseModel):
    to: Union[EmailStr, NameEmail]
    subject: str
    html: str

    def json_for_request(self):
        return {
            "from": FROM_EMAIl,
            "to": [self.to],
            "subject": self.subject,
            "html": self.html,
        }
