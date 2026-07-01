"""
Firebase Cloud Functions — 9&Self
Arquivo principal que exporta todas as functions do projeto.

Deploy de tudo:
  firebase deploy --only functions

Deploy individual:
  firebase deploy --only functions:webhookMercadoPago
  firebase deploy --only functions:webhookHotmart
  firebase deploy --only functions:webhookCreditos
"""

from webhook_mercadopago import webhookMercadoPago          # noqa: F401
from webhook_hotmart import webhookHotmart                  # noqa: F401
from webhook_creditos import webhookCreditos                # noqa: F401
from gerador_cultura_function import gerarLaudoCultura     # noqa: F401
