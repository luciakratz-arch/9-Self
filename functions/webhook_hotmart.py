"""
Firebase Cloud Function — webhookHotmart
Deploy: firebase deploy --only functions:webhookHotmart

Esta função é SEPARADA das demais — não interfere em nada existente.
Segue exatamente o mesmo padrão do webhook_mercadopago.py
"""

import json
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request

import firebase_admin
from firebase_admin import firestore
from firebase_functions import https_fn
from firebase_functions.params import StringParam

# Inicializar app (só uma vez, compartilhado com main.py)
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

# ── PARÂMETROS ──
GMAIL_PASS  = StringParam("GMAIL_PASS")
GMAIL_USER  = "luciakratz@gmail.com"
APP_URL     = "https://luciakratz-arch.github.io/9-Self/index.html"

# IDs dos produtos 9&Self na Hotmart que devem gerar código
PRODUTOS_9SELF = {'8032417'}  # Mapeamento de Perfil Avançado - 9&Self

# Token secreto opcional para validar chamadas da Hotmart
# Configure via: firebase functions:config:set hotmart.token="SEU_HOTMART_TOKEN"
HOTMART_TOKEN = StringParam("HOTMART_TOKEN")

# ── GERAR CÓDIGO ÚNICO ──
def gerar_codigo():
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choices(chars, k=6))

# ── ENVIAR E-MAIL ──
def enviar_email(destinatario, nome, codigo):
    link = f"{APP_URL}?code={codigo}"
    msg = MIMEMultipart('alternative')
    msg['Subject'] = '🎉 Seu código de acesso ao 9&Self chegou!'
    msg['From']    = f'"9&Self | Lúcia Kratz" <{GMAIL_USER}>'
    msg['To']      = destinatario

    html = f"""
    <div style="font-family:Georgia,serif;max-width:560px;margin:0 auto;background:#1a0a2e;color:#fff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#3d0a5e,#7B1D6B);padding:32px;text-align:center;">
        <h1 style="font-size:36px;margin:0;letter-spacing:-1px;">9&amp;Self</h1>
        <p style="opacity:.7;margin:8px 0 0;letter-spacing:2px;font-size:12px;">DESCUBRA SUA PERSONALIDADE</p>
      </div>
      <div style="padding:32px;">
        <p>Olá, <strong>{nome}</strong>!</p>
        <p>Sua compra foi confirmada. Aqui está seu código exclusivo de acesso:</p>
        <div style="background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:24px;text-align:center;margin:24px 0;">
          <p style="margin:0 0 8px;font-size:12px;opacity:.6;letter-spacing:2px;">SEU CÓDIGO</p>
          <p style="font-size:36px;font-weight:700;letter-spacing:6px;margin:0;color:#E8B4F8;">{codigo}</p>
        </div>
        <p>Clique no botão abaixo para acessar seu teste:</p>
        <div style="text-align:center;margin:24px 0;">
          <a href="{link}"
            style="background:linear-gradient(135deg,#7B00C4,#7B1D6B);color:#fff;padding:14px 32px;border-radius:12px;text-decoration:none;font-weight:600;display:inline-block;">
            Acessar meu teste →
          </a>
        </div>
        <p style="font-size:11px;opacity:.5;margin-top:32px;">
          Ou acesse <a href="{APP_URL}" style="color:#E8B4F8;">{APP_URL}</a>
          e insira o código <strong>{codigo}</strong> na aba <strong>Usuário</strong>.
        </p>
        <p style="font-size:11px;opacity:.5;">Dúvidas? Responda este e-mail.</p>
      </div>
    </div>
    """

    msg.attach(MIMEText(html, 'html'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS.value)
        server.sendmail(GMAIL_USER, destinatario, msg.as_string())

# ── WEBHOOK HOTMART ──
@https_fn.on_request()
def webhookHotmart(req: https_fn.Request) -> https_fn.Response:
    # Hotmart pode validar o endpoint com GET
    if req.method == 'GET':
        return https_fn.Response('OK', status=200)

    if req.method == 'OPTIONS':
        return https_fn.Response('', status=204)

    try:
        body = req.get_json(silent=True) or {}

        # ── Extrair dados do payload da Hotmart ──
        # Estrutura do webhook Hotmart v2:
        # body.event = "PURCHASE_APPROVED" ou "PURCHASE_COMPLETE"
        # body.data.purchase.transaction = ID da transação
        # body.data.purchase.status = "APPROVED" | "COMPLETE"
        # body.data.buyer.email
        # body.data.buyer.name

        event  = body.get('event', '')
        data   = body.get('data', {})

        # Aceita tanto PURCHASE_APPROVED quanto PURCHASE_COMPLETE
        eventos_validos = {'PURCHASE_APPROVED', 'PURCHASE_COMPLETE'}
        if event not in eventos_validos:
            print(f"[hotmart] Evento ignorado: {event}")
            return https_fn.Response('ignored', status=200)

        purchase = data.get('purchase', {})
        buyer    = data.get('buyer', {})
        product  = data.get('product', {})

        # ── Filtrar apenas produtos 9&Self ──
        produto_id = str(product.get('id', ''))
        if produto_id not in PRODUTOS_9SELF:
            print(f"[hotmart] Produto {produto_id} ignorado — não é 9&Self")
            return https_fn.Response('produto ignorado', status=200)

        status_compra = purchase.get('status', '').upper()
        if status_compra not in ('APPROVED', 'COMPLETE'):
            return https_fn.Response('nao aprovado', status=200)

        transacao_id = str(purchase.get('transaction', ''))
        email        = buyer.get('email', '')
        nome         = buyer.get('name', 'Cliente')

        if not email or not transacao_id:
            return https_fn.Response('dados incompletos', status=400)

        # Evitar processamento duplicado
        existente = db.collection('nself_codigos') \
            .where('pagamentoId', '==', transacao_id).get()
        if len(existente) > 0:
            print(f"[hotmart] Transação {transacao_id} já processada")
            return https_fn.Response('ja processado', status=200)

        # Gerar código único
        codigo = gerar_codigo()
        tentativas = 0
        while tentativas < 10:
            snap = db.collection('nself_codigos') \
                .where('codigo', '==', codigo).get()
            if len(snap) == 0:
                break
            codigo = gerar_codigo()
            tentativas += 1

        # Salvar no Firebase
        db.collection('nself_codigos').add({
            'codigo': codigo,
            'nomeDestinatario': nome,
            'email': email,
            'empresa': None,
            'tipo': 'PF',
            'status': 'Pendente',
            'origem': 'hotmart',
            'pagamentoId': transacao_id,
            'valorPago': purchase.get('price', {}).get('value', 0),
            'linkTeste': f"{APP_URL}?code={codigo}",
            'criadoEm': firestore.SERVER_TIMESTAMP,
        })

        # Enviar e-mail com o código
        enviar_email(email, nome, codigo)

        print(f"[hotmart] Código {codigo} gerado e enviado para {email}")
        return https_fn.Response('ok', status=200)

    except Exception as e:
        print(f"[hotmart] Erro: {e}")
        return https_fn.Response(f'erro: {str(e)}', status=500)
