"""
Firebase Cloud Function — gerarLaudoCultura
Geração do PDF de Fit Cultural / People Analytics com validação de role no backend.

Deploy: firebase deploy --only functions:gerarLaudoCultura
"""

import json
import firebase_admin
from firebase_admin import firestore, auth
from firebase_functions import https_fn
from firebase_functions.params import StringParam
import urllib.request
import tempfile
import os

if not firebase_admin._apps:
    firebase_admin.initialize_app()

db = firestore.client()

# Roles com permissão para gerar relatório de cultura
ROLES_PERMITIDOS = {'admin', 'rh', 'parceiro', 'rh_empresa'}

STORAGE_BUCKET = StringParam("STORAGE_BUCKET")  # ex: entrevista-inicial.appspot.com

def verificar_role(uid: str) -> str | None:
    """
    Verifica se o usuário tem role autorizado.
    Retorna o role ou None se não autorizado.
    """
    try:
        # Busca o role no Firestore (coleção 'usuarios')
        user_doc = db.collection('usuarios').document(uid).get()
        if not user_doc.exists:
            return None
        role = user_doc.to_dict().get('role', '').lower()
        if role in ROLES_PERMITIDOS:
            return role
        return None
    except Exception as e:
        print(f'[cultura] Erro ao verificar role: {e}')
        return None


@https_fn.on_request(
    cors=https_fn.options.CorsOptions(
        cors_origins=["*"],
        cors_methods=["POST", "OPTIONS"],
    )
)
def gerarLaudoCultura(req: https_fn.Request) -> https_fn.Response:
    if req.method == 'OPTIONS':
        return https_fn.Response('', status=204)

    if req.method != 'POST':
        return https_fn.Response('Método não permitido', status=405)

    try:
        # ── 1. Autenticação via Firebase ID Token ─────────────────────────────
        auth_header = req.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return https_fn.Response(
                json.dumps({'error': 'Token de autenticação ausente'}),
                status=401, content_type='application/json'
            )

        id_token = auth_header.split('Bearer ')[1]
        try:
            decoded = auth.verify_id_token(id_token)
            uid = decoded['uid']
        except Exception:
            return https_fn.Response(
                json.dumps({'error': 'Token inválido ou expirado'}),
                status=401, content_type='application/json'
            )

        # ── 2. Verificar Role no Firestore ────────────────────────────────────
        role = verificar_role(uid)
        if not role:
            return https_fn.Response(
                json.dumps({'error': 'Acesso negado. Permissão insuficiente.'}),
                status=403, content_type='application/json'
            )

        # ── 3. Ler dados da requisição ────────────────────────────────────────
        body = req.get_json(silent=True) or {}
        empresa_id = body.get('empresaId', '')
        if not empresa_id:
            return https_fn.Response(
                json.dumps({'error': 'empresaId obrigatório'}),
                status=400, content_type='application/json'
            )

        # ── 4. Buscar dados da empresa no Firestore ───────────────────────────
        empresa_doc = db.collection('empresas').document(empresa_id).get()
        if not empresa_doc.exists:
            return https_fn.Response(
                json.dumps({'error': 'Empresa não encontrada'}),
                status=404, content_type='application/json'
            )
        empresa_data = empresa_doc.to_dict()
        nome_empresa = empresa_data.get('nome', 'Empresa')
        cnpj         = empresa_data.get('cnpj', '—')

        # ── 5. Buscar perfis dos colaboradores da empresa ─────────────────────
        laudos = db.collection('nself_laudos') \
            .where('empresa', '==', nome_empresa).get()

        perfis = []
        for laudo in laudos:
            d = laudo.to_dict()
            tipo = d.get('tipo')
            asa  = d.get('asaDominante') or d.get('asa')
            sub  = d.get('subtipoDominante') or d.get('subtipo_dom', 'AP')
            if tipo:
                perfis.append({'tipo': int(tipo), 'asa': int(asa or 0), 'subtipo_dom': sub})

        if len(perfis) < 3:
            return https_fn.Response(
                json.dumps({'error': f'Mínimo de 3 perfis necessários. Empresa tem {len(perfis)}.'}),
                status=422, content_type='application/json'
            )

        # ── 6. Gerar PDF ──────────────────────────────────────────────────────
        from gerador_cultura import gerar_laudo_cultura

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        gerar_laudo_cultura(
            empresa=nome_empresa,
            cnpj=cnpj,
            total_colaboradores=len(perfis),
            perfis=perfis,
            output_path=tmp_path,
            solicitante=role.upper(),
        )

        # ── 7. Upload para Firebase Storage ──────────────────────────────────
        from google.cloud import storage as gcs
        bucket_name = STORAGE_BUCKET.value
        gcs_client  = gcs.Client()
        bucket      = gcs_client.bucket(bucket_name)
        blob_path   = f'laudos_cultura/{empresa_id}/cultura_{empresa_id}.pdf'
        blob        = bucket.blob(blob_path)
        blob.upload_from_filename(tmp_path, content_type='application/pdf')
        blob.make_public()
        url = blob.public_url
        os.unlink(tmp_path)

        # ── 8. Salvar referência no Firestore ─────────────────────────────────
        db.collection('empresas').document(empresa_id).update({
            'laudoCulturaUrl': url,
            'laudoCulturaGeradoEm': firestore.SERVER_TIMESTAMP,
            'laudoCulturaGeradoPor': uid,
        })

        print(f'[cultura] PDF gerado para {nome_empresa} por {uid} ({role})')
        return https_fn.Response(
            json.dumps({'url': url, 'empresa': nome_empresa, 'totalPerfis': len(perfis)}),
            status=200, content_type='application/json'
        )

    except Exception as e:
        print(f'[cultura] Erro: {e}')
        return https_fn.Response(
            json.dumps({'error': str(e)}),
            status=500, content_type='application/json'
        )
