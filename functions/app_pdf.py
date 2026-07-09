import os
import json
import tempfile
from flask import Flask, request, jsonify
from laudo_gerador import gerar_laudo
from google.cloud import storage
from params_config import STORAGE_BUCKET

app = Flask(__name__)

@app.route('/', methods=['POST', 'OPTIONS'])
def gerarLaudoPDF():
    if request.method == 'OPTIONS':
        return '', 204, {'Access-Control-Allow-Origin': '*'}

    try:
        body = request.get_json(silent=True) or {}
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

        bucket = storage.Client().bucket(STORAGE_BUCKET.value)
        blob = bucket.blob(f'laudos/{codigo_id or nome}/laudo_{tipo}_{asa}_{sub_dom}.pdf')
        blob.upload_from_filename(tmp_path, content_type='application/pdf')
        blob.make_public()
        
        os.unlink(tmp_path)
        return jsonify({'url': blob.public_url}), 200, {'Access-Control-Allow-Origin': '*'}

    except Exception as e:
        return jsonify({'error': str(e)}), 500, {'Access-Control-Allow-Origin': '*'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))