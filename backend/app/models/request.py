from pydantic import BaseModel, HttpUrl
from typing import List

class RequestURL(BaseModel):
    url: HttpUrl
