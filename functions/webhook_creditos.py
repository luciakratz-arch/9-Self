"""
Firebase Cloud Function — webhookCreditos
Recebe pagamentos aprovados de lotes de representantes e injeta créditos no Firebase.

Deploy: firebase deploy --only functions:webhookCreditos

Configure:
  firebase functions:config:set mercadopago.token="APP_USR-..."
  firebase functions:config:set gmail.pass="sua_app_password"
"""

import json
import random
import smtplib
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import firebase_admin
from firebase_admin import firestore
from firebase_functions import https_fn
from firebase_functions.params import StringParam

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

GMAIL_PASS = StringParam("GMAIL_PASS")
MP_TOKEN   = StringParam("MP_TOKEN")
GMAIL_USER = "luciakratz@gmail.com"
APP_URL    = "https://luciakratz-arch.github.io/9-Self/index.html"

# ── TABELA DE LOTES (external_reference → créditos) ──
# Configure o campo "Referência externa" ao criar o link no Mercado Pago
LOTES = {
  "lote_rep_1":   {"creditos": 1,   "faixa": 1,  "preco_unit": 40.00},
  "lote_rep_10":  {"creditos": 10,  "faixa": 1,  "preco_unit": 40.00},
  "lote_rep_50":  {"creditos": 50,  "faixa": 1,  "preco_unit": 40.00},
  "lote_rep_51":  {"creditos": 51,  "faixa": 2,  "preco_unit": 32.00},
  "lote_rep_100": {"creditos": 100, "faixa": 2,  "preco_unit": 32.00},
  "lote_rep_101": {"creditos": 101, "faixa": 3,  "preco_unit": 26.00},
  "lote_rep_150": {"creditos": 150, "faixa": 3,  "preco_unit": 26.00},
  "lote_rep_200": {"creditos": 200, "faixa": 4,  "preco_unit": 22.00},
  "lote_rep_300": {"creditos": 300, "faixa": 5,  "preco_unit": 19.00},
  "lote_rep_500": {"creditos": 500, "faixa": 7,  "preco_unit": 15.90},
  # Lotes RH/Empresa
  "lote_rh_5":    {"creditos": 5,   "faixa": 1,  "preco_unit": 71.00},
  "lote_rh_10":   {"creditos": 10,  "faixa": 2,  "preco_unit": 69.00},
  "lote_rh_20":   {"creditos": 20,  "faixa": 3,  "preco_unit": 65.00},
  "lote_rh_50":   {"creditos": 50,  "faixa": 4,  "preco_unit": 62.00},
  "lote_rh_100":  {"creditos": 100, "faixa": 5,  "preco_unit": 58.00},
}

def calcular_creditos_por_titulo(titulo: str) -> int:
    """Fallback: tenta extrair quantidade do título do item."""
    import re
    match = re.search(r'(\d+)\s*(cr[eé]ditos?|testes?|licen[cç]as?)', titulo.lower())
    if match:
        return int(match.group(1))
    return 0

def enviar_email_creditos(email, nome, creditos, saldo_atual):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'✅ {creditos} crédito(s) adicionado(s) ao seu perfil 9&Self'
    msg['From']    = f'"9&Self | Lúcia Kratz" <{GMAIL_USER}>'
    msg['To']      = email

    html = f"""
    <div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;background:#1a0a2e;color:#fff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#3d0a5e,#7B1D6B);padding:32px;text-align:center;">
        <h1 style="font-size:32px;margin:0;">9&amp;Self</h1>
        <p style="opacity:.7;margin:8px 0 0;font-size:12px;letter-spacing:2px;">REPRESENTANTE OFICIAL</p>
      </div>
      <div style="padding:32px;">
        <p>Olá, <strong>{nome}</strong>!</p>
        <p>Seu pagamento foi confirmado e os créditos foram adicionados ao seu perfil.</p>
        <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.15);border-radius:12px;padding:20px;margin:24px 0;text-align:center;">
          <p style="margin:0 0 6px;font-size:12px;opacity:.6;letter-spacing:2px;">CRÉDITOS ADICIONADOS</p>
          <p style="font-size:40px;font-weight:700;margin:0;color:#7ee8a2;">+{creditos}</p>
          <p style="font-size:13px;margin:10px 0 0;opacity:.6;">Saldo atual: <strong>{saldo_atual} créditos</strong></p>
        </div>
        <p>Acesse o sistema para gerenciar seus créditos e gerar laudos para seus clientes.</p>
        <div style="text-align:center;margin:24px 0;">
          <a href="{APP_URL}" style="background:linear-gradient(135deg,#7B00C4,#7B1D6B);color:#fff;padding:14px 32px;border-radius:12px;text-decoration:none;font-weight:600;display:inline-block;">
            Acessar o sistema →
          </a>
        </div>
        <p style="font-size:11px;opacity:.5;">Dúvidas? Responda este e-mail.</p>
      </div>
    </div>
    """
    msg.attach(MIMEText(html, 'html'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS.value)
        server.sendmail(GMAIL_USER, email, msg.as_string())

@https_fn.on_request(
    cors=https_fn.options.CorsOptions(
        cors_origins=["*"],
        cors_methods=["GET", "POST", "OPTIONS"],
    )
)
def webhookCreditos(req: https_fn.Request) -> https_fn.Response:
    if req.method == 'GET':
        return https_fn.Response('OK', status=200)
    if req.method == 'OPTIONS':
        return https_fn.Response('', status=204)

    try:
        body = req.get_json(silent=True) or {}
        tipo = body.get('type', '')
        data = body.get('data', {})

        if tipo != 'payment':
            return https_fn.Response('ignored', status=200)

        payment_id = str(data.get('id', ''))
        if not payment_id:
            return https_fn.Response('sem payment id', status=400)

        # Buscar pagamento na API do Mercado Pago
        mp_req = urllib.request.Request(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {MP_TOKEN.value}"}
        )
        with urllib.request.urlopen(mp_req) as resp:
            payment = json.loads(resp.read())

        if payment.get('status') != 'approved':
            return https_fn.Response('nao aprovado', status=200)

        # Evitar duplicatas
        dup = db.collection('nself_creditos_log') \
            .where('pagamentoId', '==', payment_id).get()
        if len(dup) > 0:
            return https_fn.Response('ja processado', status=200)

        email           = payment.get('payer', {}).get('email', '')
        external_ref    = payment.get('external_reference', '')
        titulo_item     = ''
        items           = payment.get('additional_info', {}).get('items', [])
        if items:
            titulo_item = items[0].get('title', '')

        # Determinar quantidade de créditos
        creditos = 0
        info_lote = LOTES.get(external_ref)
        if info_lote:
            creditos = info_lote['creditos']
        else:
            creditos = calcular_creditos_por_titulo(titulo_item)

        if creditos == 0:
            print(f"[creditos] Não foi possível determinar créditos para ref={external_ref}")
            return https_fn.Response('creditos indetermináveis', status=422)

        if not email:
            return https_fn.Response('sem email', status=400)

        # Buscar representante no Firebase pelo email
        reps = db.collection('representantes') \
            .where('email', '==', email).get()

        # Buscar também em nself_parceiros (novo sistema)
        parceiros_novos = db.collection('nself_parceiros') \
            .where('email', '==', email).get()

        representante_id = ''
        empresa_id = ''

        if len(reps) == 0:
            # Criar registro de representante se não existir
            novo_rep = {
                'email': email,
                'nome': payment.get('payer', {}).get('first_name', 'Representante'),
                'creditos': creditos,
                'creditosUsados': 0,
                'status': 'ativo',
                'criadoEm': firestore.SERVER_TIMESTAMP,
            }
            rep_ref = db.collection('representantes').add(novo_rep)[1]
            saldo_atual = creditos
            nome = novo_rep['nome']
        else:
            # Adicionar créditos atomicamente ao representante existente
            rep_doc = reps[0]
            rep_ref = rep_doc.reference
            representante_id = rep_doc.id
            saldo_anterior = rep_doc.to_dict().get('creditos', 0)
            saldo_atual = saldo_anterior + creditos
            nome = rep_doc.to_dict().get('nome', 'Representante')
            rep_ref.update({
                'creditos': firestore.Increment(creditos),
                'ultimaRecarga': firestore.SERVER_TIMESTAMP,
            })

        # Atualizar também nself_parceiros se existir
        if len(parceiros_novos) > 0:
            parc_doc = parceiros_novos[0]
            representante_id = parc_doc.id
            parc_doc.reference.update({
                'creditos': firestore.Increment(creditos),
                'ultimaRecarga': firestore.SERVER_TIMESTAMP,
            })

        # Identificar se é lote de empresa (RH)
        if external_ref and external_ref.startswith('lote_rh_'):
            rh_docs = db.collection('nself_empresas') \
                .where('email', '==', email).get()
            if len(rh_docs) > 0:
                empresa_id = rh_docs[0].id
                rh_docs[0].reference.update({
                    'creditos': firestore.Increment(creditos),
                    'ultimaRecarga': firestore.SERVER_TIMESTAMP,
                })

        # Registrar log da transação
        db.collection('nself_creditos_log').add({
            'email': email,
            'nome': nome,
            'creditos': creditos,
            'saldoApos': saldo_atual,
            'pagamentoId': payment_id,
            'externalRef': external_ref,
            'tituloItem': titulo_item,
            'valorPago': payment.get('transaction_amount', 0),
            'representanteId': representante_id,
            'empresaId': empresa_id,
            'criadoEm': firestore.SERVER_TIMESTAMP,
        })

        # Enviar e-mail de confirmação
        enviar_email_creditos(email, nome, creditos, saldo_atual)

        print(f"[creditos] +{creditos} créditos para {email} | saldo: {saldo_atual}")
        return https_fn.Response('ok', status=200)

    except Exception as e:
        print(f"[creditos] Erro: {e}")
        return https_fn.Response(f'erro: {str(e)}', status=500)
