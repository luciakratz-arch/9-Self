"""
Firebase Cloud Function — gerarCheckoutCreditos
Gera link de pagamento dinâmico no Mercado Pago para lotes de créditos de parceiros.

Deploy: firebase deploy --only functions:gerarCheckoutCreditos
"""

import json
import urllib.request
import urllib.parse

import firebase_admin
from firebase_admin import firestore
from firebase_functions import https_fn

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

from params_config import GMAIL_PASS, MP_TOKEN
GMAIL_USER = "luciakratz@gmail.com"
APP_URL    = "https://luciakratz-arch.github.io/9-Self/index.html"

# Tabela de lotes
LOTES = {
    "lote_rep_10":  {"creditos": 10,  "preco_unit": 40.00, "total": 400.00},
    "lote_rep_50":  {"creditos": 50,  "preco_unit": 32.00, "total": 1600.00},
    "lote_rep_100": {"creditos": 100, "preco_unit": 26.00, "total": 2600.00},
    "lote_rep_200": {"creditos": 200, "preco_unit": 22.00, "total": 4400.00},
    "lote_rep_300": {"creditos": 300, "preco_unit": 19.00, "total": 5700.00},
    "lote_rep_500": {"creditos": 500, "preco_unit": 15.90, "total": 7950.00},
}

@https_fn.on_request()
def gerarCheckoutCreditos(req: https_fn.Request) -> https_fn.Response:
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
    }

    if req.method == 'OPTIONS':
        return https_fn.Response('', status=204, headers=headers)

    try:
        body      = req.get_json(silent=True) or {}
        ref       = body.get('ref', '')
        email     = body.get('email', '')
        nome      = body.get('nome', 'Parceiro')

        lote = LOTES.get(ref)
        if not lote:
            return https_fn.Response(
                json.dumps({'error': 'Lote inválido'}),
                status=400, headers={**headers, 'Content-Type': 'application/json'}
            )

        creditos = lote['creditos']
        total    = lote['total']

        # Criar preferência no Mercado Pago
        preference = {
            "items": [{
                "title": f"9&Self — {creditos} créditos para parceiros",
                "quantity": 1,
                "unit_price": total,
                "currency_id": "BRL",
            }],
            "payer": {
                "email": email,
                "name": nome,
            },
            "external_reference": ref,
            "back_urls": {
                "success": APP_URL + "?pagamento=sucesso",
                "failure": APP_URL + "?pagamento=erro",
                "pending": APP_URL + "?pagamento=pendente",
            },
            "auto_return": "approved",
            "statement_descriptor": "9SELF CREDITOS",
            "notification_url": "https://us-central1-entrevista-inicial.cloudfunctions.net/webhookCreditos",
        }

        req_mp = urllib.request.Request(
            "https://api.mercadopago.com/checkout/preferences",
            data=json.dumps(preference).encode('utf-8'),
            headers={
                "Authorization": f"Bearer {MP_TOKEN.value}",
                "Content-Type": "application/json",
            },
            method="POST"
        )

        with urllib.request.urlopen(req_mp) as resp:
            result = json.loads(resp.read())

        init_point = result.get('init_point', '')

        return https_fn.Response(
            json.dumps({'url': init_point, 'creditos': creditos, 'total': total}),
            status=200,
            headers={**headers, 'Content-Type': 'application/json'}
        )

    except Exception as e:
        print(f"[checkout] Erro: {e}")
        return https_fn.Response(
            json.dumps({'error': str(e)}),
            status=500,
            headers={**headers, 'Content-Type': 'application/json'}
        )
