"""
Cloud Function: gerarLaudoPDF
Projeto Firebase: entrevista-inicial
Sistema: 9&Self — Avaliação de Personalidade

CORREÇÃO APLICADA (jun/2025):
  Os arquivos banco_dados_final/tipo_X.txt estão DENTRO da pasta functions/,
  no mesmo nível deste main.py. O caminho usa os.path.dirname(__file__)
  apontando diretamente para banco_dados_final/ sem subir nenhum nível.
  Um try/except por arquivo garante fallback seguro sem travar a geração.
"""

import os
import json
import tempfile
import firebase_admin
from firebase_admin import credentials, firestore, storage
from flask import jsonify
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime

# ── INICIALIZAÇÃO FIREBASE ──────────────────────────────────────────────────
if not firebase_admin._apps:
    firebase_admin.initialize_app()

db  = firestore.client()
bkt = storage.bucket()

# ── CONSTANTES ─────────────────────────────────────────────────────────────
NOMES = {
    1: "Perfeição e Excelência",
    2: "Amor e Generosidade",
    3: "Sucesso e Realização",
    4: "Identidade e Profundidade",
    5: "Conhecimento e Investigação",
    6: "Segurança e Lealdade",
    7: "Entusiasmo e Possibilidades",
    8: "Poder e Proteção",
    9: "Paz e Harmonia",
}

SUBTIPO_LABEL = {
    "sx":  "1 a 1",
    "so":  "Social",
    "sp":  "Conservação",
    "1a1": "1 a 1",
}

CORES = {
    "purple": colors.HexColor("#7B00C4"),
    "mag":    colors.HexColor("#7B1D6B"),
    "teal":   colors.HexColor("#1A9BAF"),
    "light":  colors.HexColor("#F7F4FB"),
    "dark":   colors.HexColor("#2C2C2C"),
    "gray":   colors.HexColor("#6B6B6B"),
    "border": colors.HexColor("#E2D9EF"),
    "white":  colors.white,
}

# ── CAMINHO DOS ARQUIVOS DE PERFIL ──────────────────────────────────────────
# main.py fica em  .../functions/main.py
# banco_dados_final fica em  .../banco_dados_final/  (raiz do repo)
# Logo: subimos um nível com os.path.dirname + os.pardir
_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))
_BANCO_DIR  = os.path.join(_THIS_DIR, "banco_dados_final")


def ler_perfil_tipo(tipo: int) -> str:
    """
    Lê o arquivo tipo_X.txt de banco_dados_final/.
    Retorna o conteúdo completo ou um texto-fallback seguro se o arquivo
    não for encontrado (evita que a função trave e exiba erro no botão).
    """
    caminho = os.path.join(_BANCO_DIR, f"tipo_{tipo}.txt")
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return (
            f"[Perfil do Tipo {tipo} não localizado no servidor. "
            f"Verifique se banco_dados_final/tipo_{tipo}.txt está na raiz do repositório.]"
        )
    except Exception as exc:
        return f"[Erro ao carregar perfil do Tipo {tipo}: {exc}]"


def normalizar_subtipo(raw: str) -> str:
    if not raw:
        return "sp"
    r = str(raw).lower().strip()
    if r in ("sx", "1a1", "1 a 1"):
        return "sx"
    if r in ("so", "social"):
        return "so"
    return "sp"


# ── GERAÇÃO DO PDF ──────────────────────────────────────────────────────────

def build_pdf(tipo: int, asa: int, sub_dom: str, sub_int: str, sub_rem: str,
              nome: str, cargo: str) -> bytes:
    """Monta o PDF do laudo e retorna os bytes."""

    buf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    buf.close()

    doc = SimpleDocTemplate(
        buf.name,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
        title=f"Laudo 9&Self — {nome}",
        author="9&Self | Dra. Lucia Kratz",
    )

    styles = getSampleStyleSheet()

    def estilo(name, **kw):
        base = styles["Normal"]
        return ParagraphStyle(name, parent=base, **kw)

    s_titulo   = estilo("titulo",   fontName="Helvetica-Bold", fontSize=22,
                        textColor=CORES["purple"], spaceAfter=6, alignment=TA_CENTER)
    s_sub      = estilo("sub",      fontName="Helvetica",      fontSize=12,
                        textColor=CORES["gray"],  spaceAfter=4, alignment=TA_CENTER)
    s_secao    = estilo("secao",    fontName="Helvetica-Bold", fontSize=13,
                        textColor=CORES["purple"], spaceBefore=14, spaceAfter=4)
    s_corpo    = estilo("corpo",    fontName="Helvetica",      fontSize=10,
                        textColor=CORES["dark"],  leading=15, spaceAfter=6,
                        alignment=TA_JUSTIFY)
    s_label    = estilo("label",    fontName="Helvetica-Bold", fontSize=9,
                        textColor=CORES["purple"])
    s_valor    = estilo("valor",    fontName="Helvetica",      fontSize=10,
                        textColor=CORES["dark"])
    s_rodape   = estilo("rodape",   fontName="Helvetica",      fontSize=8,
                        textColor=CORES["gray"],  alignment=TA_CENTER)

    perfil_texto = ler_perfil_tipo(tipo)

    # Separar seções por marcador === (adapte ao formato real dos seus .txt)
    secoes = [s.strip() for s in perfil_texto.split("===") if s.strip()]

    data_hoje = datetime.now().strftime("%d/%m/%Y")

    story = []

    # ── CABEÇALHO ────────────────────────────────────────────────────────────
    story.append(Paragraph("9&amp;Self", s_titulo))
    story.append(Paragraph("Avaliação de Personalidade", s_sub))
    story.append(HRFlowable(width="100%", thickness=2, color=CORES["purple"],
                             spaceAfter=12))

    # ── DADOS DO PARTICIPANTE ────────────────────────────────────────────────
    dados_tabela = [
        [Paragraph("Participante", s_label), Paragraph(nome, s_valor)],
        [Paragraph("Cargo / Função", s_label), Paragraph(cargo or "—", s_valor)],
        [Paragraph("Data de Emissão", s_label), Paragraph(data_hoje, s_valor)],
    ]
    t = Table(dados_tabela, colWidths=[4*cm, 13*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), CORES["light"]),
        ("TEXTCOLOR",  (0, 0), (0, -1), CORES["purple"]),
        ("GRID",       (0, 0), (-1, -1), 0.5, CORES["border"]),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CORES["white"], CORES["light"]]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    # ── RESULTADO ────────────────────────────────────────────────────────────
    story.append(Paragraph("Resultado da Avaliação", s_secao))

    resultado_tabela = [
        [
            Paragraph("Tipo Principal", s_label),
            Paragraph(f"Tipo {tipo} — {NOMES.get(tipo, '')}", s_valor),
        ],
        [
            Paragraph("Asa Dominante", s_label),
            Paragraph(f"Asa {asa}", s_valor),
        ],
        [
            Paragraph("Subtipo Dominante", s_label),
            Paragraph(SUBTIPO_LABEL.get(sub_dom, sub_dom), s_valor),
        ],
        [
            Paragraph("Subtipo Intermediário", s_label),
            Paragraph(SUBTIPO_LABEL.get(sub_int, sub_int), s_valor),
        ],
        [
            Paragraph("Subtipo de Menor Ênfase", s_label),
            Paragraph(SUBTIPO_LABEL.get(sub_rem, sub_rem), s_valor),
        ],
    ]
    tr = Table(resultado_tabela, colWidths=[5*cm, 12*cm])
    tr.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EDD9FF")),
        ("GRID",       (0, 0), (-1, -1), 0.5, CORES["border"]),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [CORES["white"], CORES["light"]]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(tr)
    story.append(Spacer(1, 14))

    # ── PERFIL TEXTUAL ───────────────────────────────────────────────────────
    story.append(Paragraph("Perfil de Personalidade", s_secao))
    story.append(HRFlowable(width="100%", thickness=1, color=CORES["border"],
                             spaceAfter=8))

    if secoes:
        for secao in secoes:
            linhas = secao.split("\n")
            titulo_secao = linhas[0].strip() if linhas else ""
            corpo_secao  = " ".join(l.strip() for l in linhas[1:] if l.strip())
            if titulo_secao:
                story.append(Paragraph(titulo_secao, s_secao))
            if corpo_secao:
                story.append(Paragraph(corpo_secao, s_corpo))
    else:
        # Arquivo sem marcadores === → exibe texto completo
        for para in perfil_texto.split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(para.replace("\n", " "), s_corpo))

    story.append(Spacer(1, 20))

    # ── NOTA ÉTICA ───────────────────────────────────────────────────────────
    nota = (
        "Na filosofia do Eneagrama, não existe personalidade melhor ou pior. "
        "Este laudo não é um rótulo, mas um mapa para o autodesenvolvimento. "
        "As respostas refletem a autopercepção atual; a personalidade é o ponto "
        "de partida, mas a consciência de si se fortalece com a terapia e a vivência. "
        "Acolha o seu processo e veja este laudo como um companheiro de caminhada."
    )
    story.append(
        Table([[Paragraph(nota, estilo("nota", fontName="Helvetica-Oblique",
                                       fontSize=9, textColor=CORES["gray"],
                                       alignment=TA_JUSTIFY))]],
              colWidths=[17*cm],
              style=[("BACKGROUND", (0,0), (-1,-1), CORES["light"]),
                     ("BOX",        (0,0), (-1,-1), 1, CORES["border"]),
                     ("TOPPADDING", (0,0), (-1,-1), 10),
                     ("BOTTOMPADDING", (0,0), (-1,-1), 10),
                     ("LEFTPADDING",   (0,0), (-1,-1), 12),
                     ("RIGHTPADDING",  (0,0), (-1,-1), 12)])
    )

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"Documento gerado em {data_hoje} · 9&amp;Self by A!Equipe Desenvolvimento Humano &amp; Cultural · "
        "Dra. Lucia Kratz · CRP 09/20590",
        s_rodape
    ))

    doc.build(story)

    with open(buf.name, "rb") as f:
        pdf_bytes = f.read()
    os.unlink(buf.name)
    return pdf_bytes


# ── ENTRY POINT DA CLOUD FUNCTION ──────────────────────────────────────────

def gerarLaudoPDF(request):
    """
    HTTP Cloud Function (POST).
    Espera JSON: { tipo, asa, subDom, subInt, subRem, nome, cargo, codigoId }
    Retorna JSON: { url, path }
    """
    # CORS pre-flight
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age":       "3600",
        }
        return ("", 204, headers)

    cors_headers = {"Access-Control-Allow-Origin": "*"}

    try:
        data = request.get_json(silent=True) or {}

        tipo    = int(data.get("tipo", 0))
        asa     = int(data.get("asa",  0))
        sub_dom = normalizar_subtipo(data.get("subDom", "sp"))
        sub_int = normalizar_subtipo(data.get("subInt", "so"))
        sub_rem = normalizar_subtipo(data.get("subRem", "sx"))
        nome    = str(data.get("nome",  "Participante")).strip() or "Participante"
        cargo   = str(data.get("cargo", "")).strip()
        codigo_id = str(data.get("codigoId", "")).strip()

        if tipo not in range(1, 10):
            return (jsonify({"error": f"Tipo inválido: {tipo}"}), 400, cors_headers)
        if asa not in range(1, 10):
            return (jsonify({"error": f"Asa inválida: {asa}"}), 400, cors_headers)

        # Gerar PDF
        pdf_bytes = build_pdf(tipo, asa, sub_dom, sub_int, sub_rem, nome, cargo)

        # Upload no Firebase Storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"{nome.replace(' ','_')}_{timestamp}"
        storage_path = f"laudos/9self_{nome_arquivo}.pdf"

        blob = bkt.blob(storage_path)
        blob.upload_from_string(pdf_bytes, content_type="application/pdf")
        blob.make_public()

        url = blob.public_url

        # Salvar registro no Firestore (opcional — o frontend também salva)
        if codigo_id:
            try:
                db.collection("nself_laudos_gerados").add({
                    "codigoId":   codigo_id,
                    "tipo":       tipo,
                    "asa":        asa,
                    "subDom":     sub_dom,
                    "subInt":     sub_int,
                    "subRem":     sub_rem,
                    "nome":       nome,
                    "cargo":      cargo,
                    "pdfUrl":     url,
                    "pdfPath":    storage_path,
                    "geradoEm":   firestore.SERVER_TIMESTAMP,
                })
            except Exception:
                pass  # não bloqueia a resposta se o registro falhar

        return (jsonify({"url": url, "path": storage_path}), 200, cors_headers)

    except Exception as exc:
        import traceback
        trace = traceback.format_exc()
        print(f"[gerarLaudoPDF ERROR] {exc}\n{trace}")
        return (
            jsonify({"error": str(exc), "trace": trace[-500:]}),
            500,
            cors_headers,
        )
