import os, tempfile, json
from firebase_functions import https_fn
from firebase_admin import initialize_app, storage as fb_storage
import firebase_admin

if not firebase_admin._apps:
    initialize_app()

def _cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

@https_fn.on_request()
def gerarLaudoPDF(req: https_fn.Request) -> https_fn.Response:
    # CORS preflight
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204, headers=_cors_headers())

    try:
        data = req.get_json(silent=True) or {}

        tipo    = int(data.get("tipo") or 1)
        asa_raw = data.get("asa") or data.get("asaDominante")
        sub_dom = _norm(data.get("subDom") or data.get("subtipoDominante"))
        sub_int = _norm(data.get("subInt") or data.get("subtipoIntermediario"))
        sub_rem = _norm(data.get("subRem") or data.get("subtipoRemissivo"))
        nome    = (data.get("nome") or "Participante").strip() or "Participante"
        cargo   = (data.get("cargo") or "").strip()
        cod_id  = data.get("codigoId") or "sem-codigo"

        ASAS = {1:[2,9],2:[1,3],3:[2,4],4:[3,5],5:[4,6],6:[5,7],7:[6,8],8:[7,9],9:[8,1]}
        try: asa = int(asa_raw)
        except: asa = ASAS[tipo][0]
        if asa not in ASAS.get(tipo, []): asa = ASAS[tipo][0]

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from laudo_gerador import gerar_laudo
        gerar_laudo(tipo=tipo, asa_dominante=asa,
                    subtipo_dom=sub_dom, subtipo_int=sub_int, subtipo_rem=sub_rem,
                    nome=nome, cargo=cargo, output_path=tmp_path)

        bucket    = fb_storage.bucket()
        safe_nome = nome.replace(" ", "_").replace("/", "-")
        blob_path = f"laudos/{cod_id}_{safe_nome}_tipo{tipo}.pdf"
        blob      = bucket.blob(blob_path)
        blob.upload_from_filename(tmp_path, content_type="application/pdf")
        blob.make_public()
        os.unlink(tmp_path)

        return https_fn.Response(
            json.dumps({"url": blob.public_url, "path": blob_path}),
            status=200,
            headers={**_cors_headers(), "Content-Type": "application/json"},
        )

    except Exception as e:
        import traceback
        return https_fn.Response(
            json.dumps({"error": str(e), "trace": traceback.format_exc()}),
            status=500,
            headers={**_cors_headers(), "Content-Type": "application/json"},
        )


def _norm(raw):
    if not raw: return "AP"
    m = {"ap":"AP","autopreservacao":"AP","autopreservação":"AP",
         "1a1":"1A1","1 a 1":"1A1","sex":"1A1",
         "soc":"SOC","so":"SOC","social":"SOC",
         "AP":"AP","1A1":"1A1","SOC":"SOC"}
    s = str(raw).strip()
    return m.get(s) or m.get(s.lower()) or "AP"
