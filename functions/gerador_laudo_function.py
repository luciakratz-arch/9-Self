"""
Firebase Cloud Function — gerarLaudoPDF
Recebe dados do laudo, gera o PDF via ReportLab e salva no Firebase Storage.

Deploy: firebase deploy --only functions:gerarLaudoPDF
"""

import os
import json
import tempfile
import firebase_admin
from firebase_admin import firestore, storage
from firebase_functions import https_fn
from params_config import GMAIL_PASS, MP_TOKEN, STORAGE_BUCKET

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

@https_fn.on_request()
def gerarLaudoPDF(req: https_fn.Request) -> https_fn.Response:
    # CORS
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }

    if req.method == 'OPTIONS':
        return https_fn.Response('', status=204, headers=headers)

    if req.method != 'POST':
        return https_fn.Response('Método não permitido', status=405, headers=headers)

    try:
        body = req.get_json(silent=True) or {}

        tipo      = int(body.get('tipo', 1))
        asa       = int(body.get('asa', 2))
        sub_dom   = body.get('subDom', 'AP')
        sub_int   = body.get('subInt', '1A1')
        sub_rem   = body.get('subRem', 'SOC')
        nome      = body.get('nome', 'Avaliado')
        cargo     = body.get('cargo', '')
        codigo_id = body.get('codigoId', '')

        # Normalizar subtipos
        mapa = {'sex':'1A1','SEX':'1A1','so':'SOC','SO':'SOC',
                'ap':'AP','soc':'SOC','1a1':'1A1'}
        sub_dom = mapa.get(sub_dom, sub_dom)
        sub_int = mapa.get(sub_int, sub_int)
        sub_rem = mapa.get(sub_rem, sub_rem)

        # Gerar PDF
        from laudo_gerador import gerar_laudo

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        gerar_laudo(
            tipo=tipo,
            asa_dominante=asa,
            subtipo_dom=sub_dom,
            subtipo_int=sub_int,
            subtipo_rem=sub_rem,
            nome=nome,
            cargo=cargo,
            output_path=tmp_path,
        )

        # Upload para Firebase Storage
        bucket_name = STORAGE_BUCKET.value
        bucket = storage.bucket(bucket_name)
        blob_path = f'laudos/{codigo_id or nome}/laudo_{tipo}_{asa}_{sub_dom}.pdf'
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(tmp_path, content_type='application/pdf')
        blob.make_public()
        url = blob.public_url
        os.unlink(tmp_path)

        print(f'[gerarLaudoPDF] PDF gerado para {nome} → {url}')
        return https_fn.Response(
            json.dumps({'url': url, 'path': blob_path}),
            status=200,
            content_type='application/json',
            headers=headers
        )

    except Exception as e:
        print(f'[gerarLaudoPDF] Erro: {e}')
        return https_fn.Response(
            json.dumps({'error': str(e)}),
            status=500,
            content_type='application/json',
            headers=headers
        )
