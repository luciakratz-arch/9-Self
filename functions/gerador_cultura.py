# -*- coding: utf-8 -*-
"""
9&Self — Gerador de Laudo de Cultura Organizacional
Dra. Lucia Kratz · CRP 09/20590

Motor que:
1. Recebe o agregado de perfis de uma empresa
2. Calcula o pódio das 3 forças dominantes (tríade)
3. Identifica instinto majoritário e termômetro de asas
4. Busca o arquivo triade_NN.txt correspondente
5. Gera o PDF do Relatório de Fit Cultural

Uso:
    from gerador_cultura import gerar_laudo_cultura
    gerar_laudo_cultura(
        empresa='ACME Corp',
        cnpj='00.000.000/0001-00',
        total_colaboradores=42,
        perfis=[{'tipo':1,'asa':2,'subtipo_dom':'AP'}, ...],
        output_path='/tmp/cultura_ACME.pdf',
        solicitante='RH',
    )
"""

import os
import re
import uuid
import hashlib
from datetime import datetime, timezone
from collections import Counter

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, HRFlowable, Table, TableStyle,
    PageBreak, NextPageTemplate, KeepTogether, Image
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── CAMINHOS ──────────────────────────────────────────────────────────────────
_BASE    = os.path.dirname(os.path.abspath(__file__))
_FONT_DIR = os.path.join(_BASE, 'fonts')
_DB_DIR   = os.path.join(_BASE, 'banco_dados_cultura')

# ── FONTE ─────────────────────────────────────────────────────────────────────
try:
    pdfmetrics.registerFont(TTFont('CormorantGaramond',
        os.path.join(_FONT_DIR, 'CormorantGaramond.ttf')))
    LOGO_FONT = 'CormorantGaramond'
except Exception:
    LOGO_FONT = 'Helvetica-Oblique'

# ── CORES ─────────────────────────────────────────────────────────────────────
PURP     = HexColor('#3D0A5E')
MAG      = HexColor('#7B1D6B')
LAVANDA  = HexColor('#D9C7F5')
DARK     = HexColor('#1A0030')
BRANCO   = white
VERDE    = HexColor('#1A9460')
CINZA    = HexColor('#F5F3FA')

# ── DIMENSÕES ─────────────────────────────────────────────────────────────────
PW, PH = A4
MARGIN  = 2.2 * cm
TW      = PW - 2 * MARGIN

# ── NOMES DOS TIPOS ───────────────────────────────────────────────────────────
NOMES_TIPO = {
    1: 'Perfeição e Excelência',
    2: 'Prestativo e Relacional',
    3: 'Performance e Imagem',
    4: 'Autêntico e Profundo',
    5: 'Observador e Privacidade',
    6: 'Precavido e Questionador',
    7: 'Visionário e Otimista',
    8: 'Desafiador e Controlador',
    9: 'Harmônico e Diplomático',
}

NOMES_SUBTIPO = {'AP': 'Autopreservação', '1A1': 'Um a Um', 'SOC': 'Social'}

# ── MAPEAMENTO DE TRÍADES (84 combinações de 9 tipos tomados 3 a 3) ───────────
def _gerar_mapa_triades():
    """Gera dicionário {frozenset(t1,t2,t3): numero_da_triades (01..84)}"""
    from itertools import combinations
    mapa = {}
    for i, combo in enumerate(combinations(range(1, 10), 3), start=1):
        mapa[frozenset(combo)] = f'{i:02d}'
    return mapa

MAPA_TRIADES = _gerar_mapa_triades()

# ══════════════════════════════════════════════════════════════════════════════
# ALGORITMO — CÁLCULO DO PÓDIO
# ══════════════════════════════════════════════════════════════════════════════

def calcular_podio(perfis: list) -> dict:
    """
    Recebe lista de dicts com chaves: tipo, asa, subtipo_dom
    Retorna:
      podio: [1º, 2º, 3º] tipos dominantes
      num_triades: código '01'..'84'
      instinto_maj: 'AP' | '1A1' | 'SOC'
      termometro_asas: 'EXPRESSIVAS' | 'RACIONAIS'
      contagem_tipos: Counter
      contagem_instintos: Counter
      contagem_asas: Counter
    """
    contagem_tipos     = Counter(p['tipo']        for p in perfis)
    contagem_instintos = Counter(p['subtipo_dom'] for p in perfis)
    contagem_asas      = Counter(p.get('asa', 0)  for p in perfis)

    # Pódio: 3 tipos mais frequentes
    podio = [t for t, _ in contagem_tipos.most_common(3)]
    if len(podio) < 3:
        # Preenche com tipos ausentes se empresa tem menos de 3 tipos
        for t in range(1, 10):
            if t not in podio:
                podio.append(t)
            if len(podio) == 3:
                break

    num_triades = MAPA_TRIADES.get(frozenset(podio[:3]), '01')

    # Instinto majoritário
    instinto_maj = contagem_instintos.most_common(1)[0][0] if contagem_instintos else 'AP'

    # Termômetro de asas: asas pares (2,4,6,8) = Racionais; ímpares (1,3,5,7,9) = Expressivas
    total_asas = len(perfis)
    asas_racionais   = sum(v for k, v in contagem_asas.items() if k % 2 == 0)
    asas_expressivas = total_asas - asas_racionais
    termometro_asas = 'RACIONAIS' if asas_racionais >= asas_expressivas else 'EXPRESSIVAS'

    return {
        'podio': podio,
        'num_triades': num_triades,
        'instinto_maj': instinto_maj,
        'termometro_asas': termometro_asas,
        'contagem_tipos': contagem_tipos,
        'contagem_instintos': contagem_instintos,
        'contagem_asas': contagem_asas,
    }

# ══════════════════════════════════════════════════════════════════════════════
# LEITURA DO ARQUIVO DE TRÍADE
# ══════════════════════════════════════════════════════════════════════════════

def carregar_triades(num: str) -> dict:
    """Lê banco_dados_cultura/triade_NN.txt e retorna dict de seções."""
    path = os.path.join(_DB_DIR, f'triade_{num}.txt')
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        texto = f.read()

    secoes = {}
    partes = re.split(r'=== (\w+) ===', texto)
    for i in range(1, len(partes), 2):
        chave = partes[i].strip()
        valor = partes[i+1].strip() if i+1 < len(partes) else ''
        secoes[chave] = valor
    return secoes

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE LAYOUT (mesmo padrão do laudo_gerador.py)
# ══════════════════════════════════════════════════════════════════════════════

def _make_styles():
    sBase   = ParagraphStyle('CBase', fontName='Helvetica', fontSize=10.5,
                              leading=17, textColor=DARK, spaceAfter=7,
                              alignment=TA_JUSTIFY)
    sTitulo = ParagraphStyle('CTit',  fontName=LOGO_FONT, fontSize=28,
                              leading=32, textColor=BRANCO, alignment=TA_CENTER)
    sSub    = ParagraphStyle('CSub',  fontName='Helvetica-Bold', fontSize=13,
                              leading=16, textColor=MAG, spaceAfter=4, spaceBefore=12)
    sBul    = ParagraphStyle('CBul',  fontName='Helvetica', fontSize=10.5,
                              leading=17, textColor=DARK, spaceAfter=5,
                              leftIndent=14, alignment=TA_JUSTIFY)
    sLabel  = ParagraphStyle('CLbl',  fontName='Helvetica-Bold', fontSize=10,
                              leading=14, textColor=PURP)
    sCaption= ParagraphStyle('CCap',  fontName='Helvetica', fontSize=9,
                              leading=13, textColor=HexColor('#555555'),
                              alignment=TA_CENTER)
    return sBase, sTitulo, sSub, sBul, sLabel, sCaption

def sp(h=0.3):  return Spacer(1, h * cm)
def hr():       return HRFlowable(width='100%', color=LAVANDA, thickness=0.8, spaceAfter=6)

def linhas_escrita(n=4):
    rows = [['']] * n
    t = Table(rows, colWidths=[TW], rowHeights=[18]*n)
    t.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 0.5, HexColor('#CCBBEE')),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    return t

def barra_podio(podio, contagem, total):
    """Gera tabela visual de barra de pódio dos 3 tipos."""
    sBase, *_ = _make_styles()
    sLbl = ParagraphStyle('BLbl', fontName='Helvetica-Bold', fontSize=9,
                           textColor=DARK, alignment=TA_CENTER)
    sNum = ParagraphStyle('BNum', fontName='Helvetica-Bold', fontSize=14,
                           textColor=PURP, alignment=TA_CENTER)
    sPct = ParagraphStyle('BPct', fontName='Helvetica', fontSize=8,
                           textColor=HexColor('#666'), alignment=TA_CENTER)

    medalhas = ['1º', '2º', '3º']
    rows_header = []
    rows_nome   = []
    rows_pct    = []
    for i, tipo in enumerate(podio[:3]):
        cnt = contagem.get(tipo, 0)
        pct = round(cnt / total * 100, 1) if total else 0
        rows_header.append(Paragraph(medalhas[i], sNum))
        rows_nome.append(Paragraph(NOMES_TIPO[tipo], sLbl))
        rows_pct.append(Paragraph(f'{cnt} colaboradores ({pct}%)', sPct))

    t = Table(
        [[rows_header[0], rows_header[1], rows_header[2]],
         [rows_nome[0],   rows_nome[1],   rows_nome[2]],
         [rows_pct[0],    rows_pct[1],    rows_pct[2]]],
        colWidths=[TW/3]*3
    )
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), HexColor('#F0E8FF')),
        ('BACKGROUND', (1,0), (1,-1), HexColor('#F8F4FF')),
        ('BACKGROUND', (2,0), (2,-1), HexColor('#FAF8FF')),
        ('BOX', (0,0), (-1,-1), 0.5, LAVANDA),
        ('INNERGRID', (0,0), (-1,-1), 0.3, LAVANDA),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    return t

# ══════════════════════════════════════════════════════════════════════════════
# CAPA
# ══════════════════════════════════════════════════════════════════════════════

def _capa_cb(canvas, doc):
    c = canvas
    # ── Degradê diagonal igual ao laudo_gerador aprovado ──
    c1 = HexColor('#26093F')
    c2 = HexColor('#4D2971')
    c3 = HexColor('#7B1D6B')
    n_steps = 80
    for i in range(n_steps):
        t = i / (n_steps - 1)
        if t < 0.5:
            tt = t / 0.5
            r = c1.red   + (c2.red   - c1.red)   * tt
            g = c1.green + (c2.green - c1.green) * tt
            b = c1.blue  + (c2.blue  - c1.blue)  * tt
        else:
            tt = (t - 0.5) / 0.5
            r = c2.red   + (c3.red   - c2.red)   * tt
            g = c2.green + (c3.green - c2.green) * tt
            b = c2.blue  + (c3.blue  - c2.blue)  * tt
        c.setFillColorRGB(r, g, b)
        y0 = PH * (1 - (i+1)/n_steps)
        y1 = PH * (1 - i/n_steps)
        c.rect(0, y0, PW, y1 - y0, fill=1, stroke=0)

    # ── Manchas orgânicas ──
    def mancha(cx, cy, r_max, color, alpha_max, n=10):
        for k in range(n, 0, -1):
            frac = k / n
            rad = r_max * frac
            alpha = alpha_max * (1 - frac) ** 1.5
            c.setFillColorRGB(color[0], color[1], color[2], alpha=alpha)
            c.circle(cx, cy, rad, fill=1, stroke=0)

    mancha(PW*0.92, PH*0.78, 7.5*cm, (0.85, 0.35, 0.75), 0.10)
    mancha(PW*0.06, PH*0.35, 8.5*cm, (0.45, 0.20, 0.65), 0.08)
    mancha(PW*0.85, PH*0.15, 5.5*cm, (1.0, 0.5, 0.85), 0.07)
    mancha(PW*0.15, PH*0.85, 6*cm,   (0.35, 0.15, 0.55), 0.07)

    # ── Rodapé ──
    c.saveState()
    c.setFont('Helvetica-Bold', 6.5)
    c.setFillColorRGB(1, 1, 1, alpha=0.7)
    c.drawCentredString(PW/2, 0.85*cm, 'RELATÓRIO DE FIT CULTURAL E PEOPLE ANALYTICS – 9&SELF')
    c.drawCentredString(PW/2, 0.50*cm, 'DESENVOLVIDO POR LÚCIA KRATZ E RYUZA GONÇALVES · USO RESTRITO — CONFIDENCIAL')
    c.restoreState()

def _pagina_cb(canvas, doc):
    canvas.saveState()
    # Linha do cabeçalho
    canvas.setStrokeColor(LAVANDA)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PH - 1.4*cm, PW - MARGIN, PH - 1.4*cm)
    # Nome da empresa no cabeçalho
    if hasattr(doc, '_empresa_nome'):
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(HexColor('#888888'))
        canvas.drawString(MARGIN, PH - 1.2*cm, f'| {doc._empresa_nome} |')
    # Rodapé
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(HexColor('#888888'))
    canvas.drawCentredString(PW/2, 1.0*cm,
        'RELATÓRIO DE FIT CULTURAL E PEOPLE ANALYTICS – 9&SELF')
    canvas.drawCentredString(PW/2, 0.65*cm,
        'DESENVOLVIDO POR LÚ CIA KRATZ E RYUZA GONÇALVES · USO RESTRITO — CONFIDENCIAL')
    canvas.drawRightString(PW - MARGIN, 1.0*cm, str(canvas.getPageNumber()))
    canvas.restoreState()

# ══════════════════════════════════════════════════════════════════════════════
# GERADOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def gerar_laudo_cultura(
    empresa: str,
    cnpj: str,
    total_colaboradores: int,
    perfis: list,
    output_path: str,
    solicitante: str = 'Admin',
    data_referencia: str = None,
) -> str:
    """
    Gera o PDF de Cultura Organizacional.

    perfis: lista de dicts com chaves: tipo (int), asa (int), subtipo_dom (str)
    """

    sBase, sTitulo, sSub, sBul, sLabel, sCaption = _make_styles()

    def p(t):   return Paragraph(t, sBase)
    def bl(t):  return Paragraph(f'• {t}', sBul)
    def sub(t): return Paragraph(t, sSub)

    # ── Calcular pódio ────────────────────────────────────────────────────────
    dados = calcular_podio(perfis)
    podio         = dados['podio']
    num_triades   = dados['num_triades']
    instinto_maj  = dados['instinto_maj']
    termometro    = dados['termometro_asas']
    contagem      = dados['contagem_tipos']
    cont_inst     = dados['contagem_instintos']

    # ── Carregar conteúdo da tríade ───────────────────────────────────────────
    sec = carregar_triades(num_triades)
    nome_cultura = sec.get(f'TRIADE_{num_triades}_CORE', '').split('\n')[0]
    if 'NOME:' in nome_cultura:
        nome_cultura = nome_cultura.replace('NOME:', '').strip()
    else:
        nome_cultura = f'Cultura Organizacional — Tríade {num_triades}'

    # ── Documento ─────────────────────────────────────────────────────────────
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.0*cm, bottomMargin=2.0*cm,
    )
    doc._empresa_nome = empresa

    capa_frame  = Frame(0, 0, PW, PH, leftPadding=0, rightPadding=0,
                         topPadding=0, bottomPadding=0)
    corpo_frame = Frame(MARGIN, 1.8*cm, TW, PH - 4.0*cm)

    doc.addPageTemplates([
        PageTemplate(id='capa',  frames=[capa_frame],  onPage=_capa_cb),
        PageTemplate(id='corpo', frames=[corpo_frame], onPage=_pagina_cb),
    ])

    story = [NextPageTemplate('capa')]

    # ══════════════════════════════════════════════════
    # CAPA
    # ══════════════════════════════════════════════════
    agora = datetime.now(timezone.utc)
    meses_pt = {1:'Janeiro',2:'Fevereiro',3:'Março',4:'Abril',5:'Maio',6:'Junho',
                7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
    mes_ano = f'{meses_pt[agora.month]} de {agora.year}'
    data_ref = data_referencia or agora.strftime('%d/%m/%Y')

    LAVANDA_C = HexColor('#D9C7F5')
    BRANCO_C  = HexColor('#FFFFFF')
    CINZA_C   = HexColor('#E4D9F7')

    story += [
        sp(3.6),
        Paragraph('9&amp;Self',
            ParagraphStyle('LogoC', fontName=LOGO_FONT, fontSize=50, leading=56,
                           textColor=LAVANDA_C, alignment=TA_CENTER)),
        sp(0.6),
        Paragraph('People Analytics &amp; Cultura Organizacional',
            ParagraphStyle('CTCultura', fontName='Helvetica-Bold', fontSize=18,
                           textColor=BRANCO_C, alignment=TA_CENTER, spaceAfter=0)),
        sp(1.2),
        Paragraph(empresa,
            ParagraphStyle('EmpC', fontName=LOGO_FONT, fontSize=28, leading=34,
                           textColor=LAVANDA_C, alignment=TA_CENTER)),
        sp(0.6),
        HRFlowable(width='55%', color=BRANCO_C, thickness=1.5, hAlign='CENTER'),
        sp(0.6),
        Paragraph(mes_ano,
            ParagraphStyle('DataC', fontName='Helvetica', fontSize=12,
                           textColor=BRANCO_C, alignment=TA_CENTER)),
        sp(1.8),
    ]

    # Tabela capa — mesmo padrão do laudo individual
    GLASS_BG = HexColor('#FFFFFF')
    sRL = ParagraphStyle('CRL', fontName='Helvetica-Bold', fontSize=10.5, textColor=HexColor('#3A1F5C'))
    sRV = ParagraphStyle('CRV', fontName='Helvetica', fontSize=10.5, textColor=HexColor('#3A1F5C'))
    for lbl, val in [
        ('Tríade:', nome_cultura),
        ('Colaboradores mapeados:', str(total_colaboradores)),
        ('Acesso:', f'Restrito · {solicitante} · Confidencial'),
    ]:
        t = Table([[
            Paragraph(f'<b>{lbl}</b>', sRL),
            Paragraph(val, sRV),
        ]], colWidths=[5*cm, TW-5*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), GLASS_BG),
            ('LINEBEFORE', (0,0), (0,-1), 3.5, MAG),
            ('TOPPADDING', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 9),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
        ]))
        story += [t, sp(0.15)]

    story.append(NextPageTemplate('corpo'))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════
    # DASHBOARD — PÓDIO VISUAL
    # ══════════════════════════════════════════════════
    story += [
        sub('Dashboard de Personalidade Coletiva'),
        hr(), sp(0.2),
        p(f'Análise baseada em <b>{total_colaboradores} colaboradores</b> mapeados '
          f'com referência em <b>{data_ref}</b>. A tríade dominante identificada é '
          f'<b>{nome_cultura}</b> (Tríade {num_triades}).'),
        sp(0.3),
        barra_podio(podio, contagem, total_colaboradores),
        sp(0.5),
    ]

    # Instinto majoritário e termômetro
    inst_label = NOMES_SUBTIPO.get(instinto_maj, instinto_maj)
    story += [
        KeepTogether([
            sub('Modificadores Dinâmicos'),
            hr(), sp(0.1),
            Table([
                [Paragraph('Instinto Majoritário:', sLabel),
                 Paragraph(f'{inst_label} ({instinto_maj})', sBase)],
                [Paragraph('Termômetro de Conflito das Asas:', sLabel),
                 Paragraph(termometro, sBase)],
            ], colWidths=[6*cm, TW-6*cm], style=TableStyle([
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('LINEBELOW', (0,0), (-1,-1), 0.3, LAVANDA),
            ])),
        ]),
        sp(0.5),
    ]

    # ══════════════════════════════════════════════════
    # SEÇÕES DO ARQUIVO DE TRÍADE
    # ══════════════════════════════════════════════════
    def limpar_emoji(txt):
        """Remove emojis que não renderizam em PDF ReportLab."""
        return re.sub(r'[\U0001F300-\U0001FFFF✍️⚠️💥🔬📋🌡️🏗️🚀🎯🧠✏️📝]+', '', txt).strip()

    def md_para_rl(txt):
        """Converte markdown para ReportLab: **bold**, *italic*. Remove emojis problemáticos."""
        txt = re.sub(r'[\U0001F300-\U0001FFFF✍️⚠️💥🔬📋🌡️🏗️🚀🎯🧠]+', '', txt)
        txt = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', txt)
        txt = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', txt)
        return txt.strip()

    # Mapeamento de filtros de opção dinâmica
    # Para seções de Instintos: só mostra o bloco que bate com instinto_maj
    # Para seções de Asas: só mostra o bloco que bate com termometro
    FILTRO_INSTINTO = {'AP': 'ap', '1A1': '1a1', 'SOC': 'soc'}
    FILTRO_ASAS     = {'EXPRESSIVAS': 'ativas', 'RACIONAIS': 'recuadas'}

    def opcao_ativa(linha, chave_secao):
        """Retorna True se a linha de opção deve ser exibida conforme o resultado da empresa."""
        l = linha.lower()
        if 'instinto' in chave_secao.lower() or 'instintos' in chave_secao.lower():
            chave = FILTRO_INSTINTO.get(instinto_maj, '')
            # "• Opção AP:" ou "• Opção SOC:" ou "• Opção 1A1:"
            match = re.match(r'^[•]?\s*opção\s+(\w+)\s*[:.]', l)
            if match:
                return match.group(1).lower() == chave
        if 'asas' in chave_secao.lower():
            chave = FILTRO_ASAS.get(termometro, '')
            # "• Opção ASAS_RECUADAS:" ou "• Opção ASAS_ATIVAS:"
            match = re.match(r'^[•]?\s*opção\s+asas_(\w+)\s*[:.]', l)
            if match:
                return match.group(1).lower() == chave
        return None  # não é linha de opção, renderizar normalmente

    def renderizar_secao(chave_secao, titulo_secao, page_break=True):
        conteudo = sec.get(chave_secao, '').strip()
        if not conteudo:
            return
        if page_break:
            story.append(PageBreak())
        else:
            story.append(sp(0.5))
        story.append(sub(titulo_secao))
        story.append(hr())
        story.append(sp(0.1))

        # Para seções com opções dinâmicas, identifica qual bloco mostrar
        eh_secao_opcoes = any(x in chave_secao.upper() for x in ['INSTINTO', 'ASAS'])
        bloco_ativo = None   # None = fora de qualquer bloco de opção; True = dentro do bloco certo; False = bloco errado

        sSubSecao = ParagraphStyle('SubSec', fontName='Helvetica-Bold', fontSize=11,
                                    textColor=PURP, spaceBefore=14, spaceAfter=4, leading=15)
        sRH = ParagraphStyle('RHItem', fontName='Helvetica-Bold', fontSize=10.5,
                               textColor=PURP, spaceBefore=10, spaceAfter=3, leading=14)

        linhas = [l.rstrip() for l in conteudo.split('\n')]
        i = 0
        while i < len(linhas):
            linha = linhas[i].strip()
            i += 1

            if not linha:
                continue
            if re.match(r'^(NOME|COMPOSIÇÃO|COMPOSICAO):', linha):
                continue
            if re.match(r'^\[.+\]$', linha):
                continue
            # Ignorar separador "=== MATRIZ DO PLANO ===" que às vezes vaza
            if re.match(r'^===', linha):
                continue

            # ── Detecção de bloco de opção dinâmica (Instinto / Asas) ──────────
            if eh_secao_opcoes and re.match(r'^•?\s*opção\s+', linha.lower()):
                resultado = opcao_ativa(linha, chave_secao)
                if resultado is True:
                    bloco_ativo = True
                    # Renderiza o título da opção sem "Opção AP:" etc — usa subtítulo limpo
                    txt = re.sub(r'^•?\s*Opção\s+\w+[:\s]*', '', linha, flags=re.IGNORECASE).strip()
                    if txt:
                        story.append(Paragraph(md_para_rl(txt), sSubSecao))
                elif resultado is False:
                    bloco_ativo = False
                continue

            # Pular conteúdo de blocos de opção não selecionados
            if eh_secao_opcoes and bloco_ativo is False:
                # Checar se chegamos num novo bloco de opção
                if re.match(r'^•?\s*opção\s+', linha.lower()):
                    pass  # será tratado na próxima iteração
                continue

            # ── Numeração como subtítulo: "1. IDENTIDADE DA..." ────────────────
            if re.match(r'^\d+\.\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+$', linha):
                story.append(sp(0.2))
                story.append(Paragraph(linha, sSubSecao))
                continue

            # ── "> 🚀 **TÍTULO:**" — destaque com emoji (remove emoji, mantém texto) ──
            if re.match(r'^>\s*[\U0001F300-\U0001FFFF⚠️💥🔬📋🌡️🏗️]+\s*\*\*', linha):
                txt = re.sub(r'^>\s*', '', linha)
                # Remove emojis que não renderizam em PDF
                txt = re.sub(r'[\U0001F300-\U0001FFFF⚠️💥🔬📋🌡️🏗️]+\s*', '', txt)
                txt = md_para_rl(txt)
                story.append(Paragraph(txt, ParagraphStyle('DestaqIcon',
                    fontName='Helvetica-Bold', fontSize=11, textColor=PURP,
                    spaceBefore=12, spaceAfter=4, leading=16)))
                continue

            # ── "• CONTRATAÇÃO:" ou "• TREINAMENTO:" — itens de RH ──────────
            if re.match(r'^•\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\(\)]+:', linha) and not re.match(r'^•\s*opção', linha.lower()):
                txt = md_para_rl(re.sub(r'^•\s*', '', linha))
                story.append(Paragraph(txt, sRH))
                continue

            # ── "> * item" — bullet em bloco citado ─────────────────────────
            if re.match(r'^>\s*\*\s', linha):
                txt = md_para_rl(re.sub(r'^>\s*\*\s*', '', linha))
                story.append(Paragraph(f'• {txt}', sBul))
                if '✍️' in txt:
                    story.append(sp(0.1)); story.append(linhas_escrita(5)); story.append(sp(0.2))
                continue

            # ── "> texto" — itálico/citação ──────────────────────────────────
            if linha.startswith('>'):
                txt = md_para_rl(re.sub(r'^>\s*', '', linha))
                story.append(Paragraph(f'<i>{txt}</i>', sBase))
                if '✍️' in txt:
                    story.append(sp(0.1)); story.append(linhas_escrita(5)); story.append(sp(0.2))
                continue

            # ── "* item" ou "• item" — bullet simples ───────────────────────
            if re.match(r'^[\*•]\s', linha):
                txt = md_para_rl(re.sub(r'^[\*•]\s*', '', linha))
                story.append(Paragraph(f'• {txt}', sBul))
                if '✍️' in txt:
                    story.append(sp(0.1)); story.append(linhas_escrita(5)); story.append(sp(0.2))
                continue

            # ── "1. texto" com conteúdo ─────────────────────────────────────
            if re.match(r'^\d+\.\s+\S', linha) and not re.match(r'^\d+\.\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+$', linha):
                txt = md_para_rl(linha)
                story.append(p(txt))
                if '✍️' in txt:
                    story.append(sp(0.1)); story.append(linhas_escrita(5)); story.append(sp(0.2))
                continue

            # ── Texto normal ─────────────────────────────────────────────────
            txt = md_para_rl(limpar_emoji(linha))
            story.append(p(txt))
            if '✍️' in txt:
                story.append(sp(0.1)); story.append(linhas_escrita(5)); story.append(sp(0.2))

    prefixo = f'TRIADE_{num_triades}'
    renderizar_secao(f'{prefixo}_CORE',               'Identidade da Personalidade Coletiva')
    renderizar_secao(f'{prefixo}_INSTINTOS',          'Dinâmica Espacial dos Instintos', page_break=False)
    renderizar_secao(f'{prefixo}_ASAS',               'Termômetro de Conflito das Asas', page_break=False)
    renderizar_secao(f'{prefixo}_ZONA_SOMBRA',        'Zona de Sombra e Gestão de Conflito')
    renderizar_secao(f'{prefixo}_GESTAO_RH',          'Diretrizes de Gestão de Pessoas')
    renderizar_secao(f'{prefixo}_AUDITORIA_INTERATIVA','Auditoria Cultural: Culture Gap e Plano de Ação')

    # ══════════════════════════════════════════════════
    # ASSINATURA DIGITAL
    # ══════════════════════════════════════════════════
    hash_uuid = str(uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f'{empresa}-{num_triades}-{instinto_maj}-{termometro}-{agora.isoformat()}'
    )).upper()
    data_hora_fmt = agora.strftime('%d/%m/%Y %H:%M:%S UTC')

    sSeloTitulo = ParagraphStyle('SeloTit', fontName='Helvetica-Bold', fontSize=12,
                                  textColor=VERDE, spaceAfter=10)
    sSeloLabel  = ParagraphStyle('SeloLbl', fontName='Helvetica-Bold', fontSize=9.5,
                                  textColor=DARK, leading=13)
    sSeloValor  = ParagraphStyle('SeloVal', fontName='Helvetica', fontSize=9.5,
                                  textColor=DARK, leading=13)
    sSeloRodape = ParagraphStyle('SeloRod', fontName='Helvetica', fontSize=9,
                                  textColor=HexColor('#666666'), spaceBefore=10)

    selo_tabela = Table([
        [Paragraph('Aprovador:', sSeloLabel),             Paragraph('Dra. Lucia Kratz', sSeloValor)],
        [Paragraph('Registro Profissional:', sSeloLabel), Paragraph('CRP 09/20590', sSeloValor)],
        [Paragraph('Empresa:', sSeloLabel),               Paragraph(empresa, sSeloValor)],
        [Paragraph('CNPJ:', sSeloLabel),                  Paragraph(cnpj, sSeloValor)],
        [Paragraph('Data e Hora (UTC):', sSeloLabel),     Paragraph(data_hora_fmt, sSeloValor)],
        [Paragraph('Hash UUID de Validação:', sSeloLabel),Paragraph(hash_uuid, sSeloValor)],
    ], colWidths=[5.5*cm, 9*cm])
    selo_tabela.hAlign = 'LEFT'
    selo_tabela.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (0,-1), 10),
        ('LINEBELOW', (0,0), (-1,-2), 0.3, HexColor('#CCCCCC')),
    ]))

    story += [
        sp(1.0),
        KeepTogether([
            Paragraph('✓ DOCUMENTO ASSINADO ELETRONICAMENTE', sSeloTitulo),
            selo_tabela,
            Paragraph(
                'Este relatório é confidencial e de uso exclusivo para Administradores, '
                'RH e Parceiros credenciados. A divulgação não autorizada é vedada. '
                'Gerado automaticamente pelo sistema 9&Self.',
                sSeloRodape
            ),
            sp(0.3),
            Paragraph(
                'Doutora em Psicologia · Especialista TCC, Neuromodulação e Musicoterapia · Goiânia, GO',
                ParagraphStyle('AssInfo', fontName='Helvetica', fontSize=9,
                                textColor=DARK, alignment=TA_LEFT, leading=14)
            ),
        ]),
    ]

    doc.build(story)
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
# TESTE LOCAL
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    perfis_teste = [
        {'tipo': 1, 'asa': 2, 'subtipo_dom': 'AP'},
        {'tipo': 1, 'asa': 9, 'subtipo_dom': 'SOC'},
        {'tipo': 2, 'asa': 1, 'subtipo_dom': '1A1'},
        {'tipo': 2, 'asa': 3, 'subtipo_dom': 'SOC'},
        {'tipo': 2, 'asa': 3, 'subtipo_dom': 'AP'},
        {'tipo': 3, 'asa': 2, 'subtipo_dom': 'SOC'},
        {'tipo': 3, 'asa': 4, 'subtipo_dom': '1A1'},
        {'tipo': 7, 'asa': 6, 'subtipo_dom': 'AP'},
    ]
    out = gerar_laudo_cultura(
        empresa='ACME Corp Teste',
        cnpj='00.000.000/0001-00',
        total_colaboradores=len(perfis_teste),
        perfis=perfis_teste,
        output_path='/home/claude/cultura_teste.pdf',
        solicitante='Admin',
    )
    print('OK ->', out)
