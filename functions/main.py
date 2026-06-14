"""
Firebase Cloud Function — gerarLaudoPDF
Projeto: entrevista-inicial
Runtime: python312
"""

import os, tempfile
from firebase_functions import https_fn
from firebase_admin import initialize_app, storage as fb_storage
import firebase_admin

if not firebase_admin._apps:
    initialize_app()

@https_fn.on_request(
    cors=https_fn.options.CorsOptions(
        cors_origins=["https://luciakratz.github.io", "http://localhost", "*"],
        cors_methods=["POST", "OPTIONS"],
    )
)
def gerarLaudoPDF(req: https_fn.Request) -> https_fn.Response:
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)

    try:
        data = req.get_json(silent=True) or {}

        # Sanitizar todos os campos — nunca enviar None para o gerador
        tipo     = int(data.get("tipo") or 1)
        asa_raw  = data.get("asa") or data.get("asaDominante")
        sub_dom  = _norm_sub(data.get("subDom") or data.get("subtipoDominante"))
        sub_int  = _norm_sub(data.get("subInt") or data.get("subtipoIntermediario"))
        sub_rem  = _norm_sub(data.get("subRem") or data.get("subtipoRemissivo"))
        nome     = (data.get("nome") or "Participante").strip() or "Participante"
        cargo    = (data.get("cargo") or "").strip()
        cod_id   = data.get("codigoId") or "sem-codigo"

        # Validar asa
        ASAS = {1:[2,9],2:[1,3],3:[2,4],4:[3,5],5:[4,6],6:[5,7],7:[6,8],8:[7,9],9:[8,1]}
        try:
            asa = int(asa_raw)
        except Exception:
            asa = ASAS[tipo][0]
        if asa not in ASAS.get(tipo, []):
            asa = ASAS[tipo][0]

        # Gerar PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from laudo_gerador import gerar_laudo

        gerar_laudo(
            tipo=tipo, asa_dominante=asa,
            subtipo_dom=sub_dom, subtipo_int=sub_int, subtipo_rem=sub_rem,
            nome=nome, cargo=cargo,
            output_path=tmp_path,
        )

        # Upload para Firebase Storage
        bucket    = fb_storage.bucket()
        safe_nome = nome.replace(" ", "_").replace("/", "-")
        blob_path = f"laudos/{cod_id}_{safe_nome}_tipo{tipo}.pdf"
        blob      = bucket.blob(blob_path)
        blob.upload_from_filename(tmp_path, content_type="application/pdf")
        blob.make_public()
        url = blob.public_url

        os.unlink(tmp_path)

        return https_fn.Response(
            {"url": url, "path": blob_path},
            status=200,
            mimetype="application/json",
        )

    except Exception as e:
        import traceback
        return https_fn.Response(
            {"error": str(e), "trace": traceback.format_exc()},
            status=500,
            mimetype="application/json",
        )


def _norm_sub(raw):
    """Normaliza qualquer valor de subtipo para AP | 1A1 | SOC."""
    if not raw:
        return "AP"
    MAP = {
        "ap": "AP", "autopreservacao": "AP", "autopreservação": "AP",
        "1a1": "1A1", "1 a 1": "1A1", "sex": "1A1",
        "soc": "SOC", "so": "SOC", "social": "SOC",
        "AP": "AP", "1A1": "1A1", "SOC": "SOC",
    }
    return MAP.get(str(raw).strip()) or MAP.get(str(raw).strip().lower()) or "AP"
