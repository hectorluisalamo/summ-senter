from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Literal

class AnalyzeRequest(BaseModel):
    url: Optional[HttpUrl] = None
    html: Optional[str] = None
    text: Optional[str] = None
    lang: Optional[Literal['en', 'es']] = None
    class Config: extra = 'forbid'
    
class AnalyzeResponse(BaseModel):
    id: str
    summary: str
    key_sentences: list[str]
    sentiment: Literal['positive', 'neutral', 'negative']
    confidence: float
    tokens: int
    latency_ms: int
    costs_cents: int
    model_version: str
    cache_hit: bool