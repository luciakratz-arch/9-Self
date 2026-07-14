import os
import json
import tempfile
import urllib.request
from flask import Flask, request, jsonify
from laudo_gerador import gerar_laudo
from google.cloud import storage
from params_config import STORAGE_BUCKET, MP_TOKEN

app = Flask(__name__)

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
}

APP_URL = 'https://luciakratz-arch.github.io/9-Self/index.html'

LOTES = {
    "lote_rep_10":  {"creditos": 10,  "total": 400.00},
    "lote_rep_50":  {"creditos": 50,  "total": 1600.00},
    "lote_rep_100": {"creditos": 100, "total": 2600.00},
    "lote_rep_200": {"creditos": 200, "total": 4400.00},
    "lote_rep_300": {"creditos": 300, "total": 5700.00},
    "lote_rep_500": {"creditos": 500, "total": 7950.00},
    "lote_rh_5":    {"creditos": 5,   "total": 1235.00},
    "lote_rh_10":   {"creditos": 10,  "total": 2470.00},
    "lote_rh_20":   {"creditos": 20,  "total": 4600.00},
    "lote_rh_50":   {"creditos": 50,  "total": 10500.00},
    "lote_rh_100":  {"creditos": 100, "total": 19000.00},
}

@app.route('/', methods=['POST', 'OPTIONS'])
def gerarLaudoPDF():
    if request.method == 'OPTIONS':
        return '', 204, CORS_HEADERS
    try:
        body      = request.get_json(silent=True) or {}
        tipo      = int(body.get('tipo', 1))
        asa       = int(body.get('asa', 2))
        sub_dom   = body.get('subDom', 'AP')
        sub_int   = body.get('subInt', '1A1')
        sub_rem   = body.get('subRem', 'SOC')
        nome      = body.get('nome', 'Avaliado')
        cargo     = body.get('cargo', '')
        codigo_id = body.get('codigoId', '')

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        gerar_laudo(
            tipo=tipo, asa_dominante=asa,
            subtipo_dom=sub_dom, subtipo_int=sub_int, subtipo_rem=sub_rem,
            nome=nome, cargo=cargo, output_path=tmp_path,
        )

        import time
        bucket = storage.Client().bucket(STORAGE_BUCKET.value)
        blob = bucket.blob(f'laudos/{codigo_id or nome}/laudo_{tipo}_{asa}_{sub_dom}_{int(time.time())}.pdf')
        blob.upload_from_filename(tmp_path, content_type='application/pdf')
        blob.make_public()
        os.unlink(tmp_path)
        return jsonify({'url': blob.public_url}), 200, CORS_HEADERS

    except Exception as e:
        return jsonify({'error': str(e)}), 500, CORS_HEADERS


@app.route('/checkout', methods=['POST', 'OPTIONS'])
def gerarCheckout():
    if request.method == 'OPTIONS':
        return '', 204, CORS_HEADERS
    try:
        body  = request.get_json(silent=True) or {}
        ref   = body.get('ref', '')
        email = body.get('email', '')
        nome  = body.get('nome', 'Parceiro')

        lote = LOTES.get(ref)
        if not lote:
            return jsonify({'error': 'Lote inválido'}), 400, CORS_HEADERS

        preference = {
            "items": [{
                "title": f"9&Self — {lote['creditos']} créditos",
                "quantity": 1,
                "unit_price": lote['total'],
                "currency_id": "BRL",
            }],
            "payer": {"email": email, "name": nome},
            "external_reference": ref,
            "back_urls": {
                "success": APP_URL + "?pagamento=sucesso",
                "failure": APP_URL + "?pagamento=erro",
                "pending": APP_URL + "?pagamento=pendente",
            },
            "auto_return": "approved",
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

        return jsonify({'url': result.get('init_point', '')}), 200, CORS_HEADERS

    except Exception as e:
        return jsonify({'error': str(e)}), 500, CORS_HEADERS


@app.route('/notificar-solicitacao', methods=['POST','OPTIONS'])
def notificarSolicitacao():
    if request.method=='OPTIONS': return '',204,CORS_HEADERS
    try:
        import smtplib, os
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        body   = request.get_json(silent=True) or {}
        nome   = body.get('nome','—')
        email  = body.get('email','—')
        wpp    = body.get('whatsapp','—')
        tipo   = body.get('tipo','—')
        origem = body.get('origem','Direto')

        TIPO_LABEL = {
            'pf_dev':'PF com Devolutiva (R$597)',
            'pf_std':'PF sem Devolutiva (R$297)',
            'empresa':'Empresa / RH',
            'parceiro':'Solicitação de Parceiro'
        }

        gmail_user = 'luciakratz@gmail.com'
        gmail_pass = os.environ.get('GMAIL_PASS','')
        if not gmail_pass:
            return jsonify({'ok':False,'msg':'GMAIL_PASS não configurado'}), 200, CORS_HEADERS

        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'[9&Self] Nova solicitação — {nome}'
        msg['From']    = f'"9&Self Sistema" <{gmail_user}>'
        msg['To']      = gmail_user

        html = f"""
        <div style="font-family:sans-serif;max-width:500px;">
          <h2 style="color:#3A1F5C;">📥 Nova Solicitação de Cadastro</h2>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:8px;color:#888;">Nome</td><td style="padding:8px;"><strong>{nome}</strong></td></tr>
            <tr style="background:#f9f9f9;"><td style="padding:8px;color:#888;">E-mail</td><td style="padding:8px;">{email}</td></tr>
            <tr><td style="padding:8px;color:#888;">WhatsApp</td><td style="padding:8px;">{wpp}</td></tr>
            <tr style="background:#f9f9f9;"><td style="padding:8px;color:#888;">Tipo</td><td style="padding:8px;">{TIPO_LABEL.get(tipo,tipo)}</td></tr>
            <tr><td style="padding:8px;color:#888;">Origem</td><td style="padding:8px;">{origem}</td></tr>
          </table>
          <p style="margin-top:16px;">
            <a href="https://luciakratz-arch.github.io/9-Self/index.html"
               style="background:#7B00C4;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;">
              Abrir Painel 9&amp;Self
            </a>
          </p>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, gmail_user, msg.as_string())

        return jsonify({'ok':True}), 200, CORS_HEADERS
    except Exception as e:
        print(f'[notificar] Erro: {e}')
        return jsonify({'ok':False,'error':str(e)}), 200, CORS_HEADERS


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
