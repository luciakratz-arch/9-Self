"""
Firebase Cloud Function — gerarLaudoPDF
Deploy: firebase deploy --only functions

Dependências (requirements.txt):
  firebase-functions
  firebase-admin
  reportlab
  pypdf
"""

import os, io, tempfile
from firebase_functions import https_fn
from firebase_admin import initialize_app, storage as fb_storage
import firebase_admin

# Inicializar app (uma vez)
if not firebase_admin._apps:
    initialize_app()

# Importar o gerador local (suba junto com as functions)
import sys
sys.path.insert(0, os.path.dirname(__file__))

@https_fn.on_request(cors=https_fn.options.CorsOptions(
    cors_origins=["https://luciakratz.github.io", "http://localhost"],
    cors_methods=["POST", "OPTIONS"],
))
def gerarLaudoPDF(req: https_fn.Request) -> https_fn.Response:
    if req.method == 'OPTIONS':
        return https_fn.Response('', status=204)

    try:
        data = req.get_json(silent=True) or {}
        tipo       = int(data.get('tipo', 1))
        asa        = int(data.get('asa', 2))
        sub_dom    = data.get('subDom', 'AP').upper()
        sub_int    = data.get('subInt', '1A1').upper()
        sub_rem    = data.get('subRem', 'SOC').upper()
        nome       = data.get('nome', 'Participante')
        cargo      = data.get('cargo', '')
        codigo_id  = data.get('codigoId', '')

        # Gerar PDF em memória
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        from laudo_gerador import gerar_laudo
        gerar_laudo(
            tipo=tipo, asa_dominante=asa,
            subtipo_dom=sub_dom, subtipo_int=sub_int, subtipo_rem=sub_rem,
            nome=nome, cargo=cargo,
            output_path=tmp_path,
        )

        # Upload para Firebase Storage
        bucket = fb_storage.bucket()
        blob_path = f'laudos/{codigo_id or nome.replace(" ","_")}_tipo{tipo}.pdf'
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(tmp_path, content_type='application/pdf')
        blob.make_public()
        url = blob.public_url

        os.unlink(tmp_path)

        return https_fn.Response(
            {'url': url, 'path': blob_path},
            status=200,
            mimetype='application/json',
        )

    except Exception as e:
        import traceback
        return https_fn.Response(
            {'error': str(e), 'trace': traceback.format_exc()},
            status=500,
            mimetype='application/json',
        )
