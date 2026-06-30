# -*- coding: utf-8 -*-
"""
9&Self — Gerador de Laudo PDF (parametrizado)
Dra. Lucia Kratz · CRP 09/20590

Lê o conteúdo de /home/claude/banco_dados_final/tipo_N.txt e monta o PDF
com a mesma estrutura visual aprovada (laudo_9self_FINAL_v5_codigo.py),
agora reutilizável para qualquer combinação de tipo / asa / subtipo.

Uso:
    from laudo_gerador import gerar_laudo
    gerar_laudo(
        tipo=1, asa_dominante=2,
        subtipo_dom='AP', subtipo_int='1A1', subtipo_rem='SOC',
        nome='Fabiano de Sousa Vaz de Campos',
        cargo='Diretor - CIRO',
        output_path='/home/claude/laudo_saida.pdf',
    )
"""

import re
import os
import hashlib
import uuid
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, HRFlowable, Table, TableStyle,
    PageBreak, NextPageTemplate, KeepTogether, Image
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_JUSTIFY
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
_IMG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'imagens')

def imagem_tipo(tipo, sufixo='', largura_cm=13):
    """
    Carrega imagens/0{tipo}{sufixo}.jpg de forma segura.
    sufixo='' -> imagem principal (ex: 01.jpg)
    sufixo='b' -> imagem secundária (ex: 01b.jpg)
    Retorna None se o arquivo não existir (não quebra o PDF).
    """
    nome_arquivo = f'0{tipo}{sufixo}.jpg'
    caminho = os.path.join(_IMG_DIR, nome_arquivo)
    if not os.path.exists(caminho):
        return None
    try:
        img = Image(caminho, width=largura_cm * cm, height=None)
        # Mantém proporção: recalcula altura com base na largura real da imagem
        from PIL import Image as PILImage
        with PILImage.open(caminho) as pil_img:
            ratio = pil_img.height / pil_img.width
        img.drawHeight = largura_cm * cm * ratio
        img.drawWidth  = largura_cm * cm
        img.hAlign = 'CENTER'
        return img
    except Exception:
        return None

try:
    pdfmetrics.registerFont(TTFont('CormorantGaramond',
        os.path.join(_FONT_DIR, 'CormorantGaramond.ttf')))
    LOGO_FONT = 'CormorantGaramond'
except Exception:
    try:
        pdfmetrics.registerFont(TTFont('LiberationSerif-Italic',
            '/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf'))
        LOGO_FONT = 'LiberationSerif-Italic'
    except Exception:
        LOGO_FONT = 'Helvetica-Oblique'

# ══════════════════════════════════════════════════════════════════════════
# CORES DA MARCA (roxo/violeta)
# ══════════════════════════════════════════════════════════════════════════
MAG   = HexColor('#7B04B4')
TEAL  = HexColor('#403071')
DARK  = HexColor('#2C2C2C')
GMID  = HexColor('#666666')
GLT   = HexColor('#F5F3F7')
TBOX  = HexColor('#EFE6F9')
MBOX  = HexColor('#F7EFF5')
GLIN  = HexColor('#DDDDDD')
WHITE = white

PW, PH = A4
ML, MR, MT, MB = 2.4*cm, 2.4*cm, 2.5*cm, 1.8*cm
TW = PW - ML - MR

BANCO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'banco_dados_final')


# ══════════════════════════════════════════════════════════════════════════
# METADADOS FIXOS DOS 9 TIPOS
# ══════════════════════════════════════════════════════════════════════════
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

NOMES_SUBTIPO = {
    'AP':  'Autopreservação',
    '1A1': '1 a 1',
    'SOC': 'Social',
}

LABELS_SUBTIPO_LONGO = {
    'AP':  'Autopreservação',
    '1A1': 'Um a Um',
    'SOC': 'Social',
}


def asas_do_tipo(tipo):
    """Retorna (asa_anterior, asa_seguinte) no ciclo 1..9."""
    anterior = 9 if tipo == 1 else tipo - 1
    seguinte = 1 if tipo == 9 else tipo + 1
    return anterior, seguinte


def chave_subtipo(dom, intermed, rem):
    """Monta a chave SUBTIPO_X_Y_Z usada no banco de dados."""
    return f"SUBTIPO_{dom}_{intermed}_{rem}"


# ══════════════════════════════════════════════════════════════════════════
# PARSER DO BANCO DE DADOS
# ══════════════════════════════════════════════════════════════════════════
def carregar_secoes(tipo):
    """Lê tipo_N.txt e retorna dict {NOME_SECAO: texto}."""
    path = os.path.join(BANCO_DIR, f"tipo_{tipo}.txt")
    with open(path, encoding='utf-8') as f:
        txt = f.read()
    secs = dict(re.findall(r'=== (\w+) ===\n(.*?)(?=\n=== |\Z)', txt, re.S))
    return {k: v.strip() for k, v in secs.items()}


def split_pipes(texto):
    """Divide um texto por ' | ' em lista de itens, removendo espaços extras.
    Se não houver '|', tenta dividir por linhas em branco (\\n\\n)."""
    if '|' in texto:
        return [item.strip() for item in texto.split('|') if item.strip()]
    partes = [t.strip() for t in re.split(r'\n\s*\n', texto.strip()) if t.strip()]
    return partes if len(partes) > 1 else ([texto.strip()] if texto.strip() else [])


def split_double_pipes(texto):
    """Divide por ' || ' (usado em HABITOS)."""
    return [item.strip() for item in texto.split('||') if item.strip()]


def split_titulo_texto(item, sep=':'):
    """Separa 'Título: texto...' em (titulo, texto). Se não houver ':', retorna (None, item)."""
    if sep in item:
        titulo, _, resto = item.partition(sep)
        return titulo.strip() + sep, resto.strip()
    return None, item.strip()


# ══════════════════════════════════════════════════════════════════════════
# ESTILOS
# ══════════════════════════════════════════════════════════════════════════
sBody  = ParagraphStyle('Body',     fontName='Helvetica',         fontSize=10.5, leading=17, textColor=DARK, spaceAfter=7,  alignment=TA_JUSTIFY)
sSecT  = ParagraphStyle('SecT',     fontName='Helvetica-Bold',    fontSize=14,   leading=19, textColor=MAG,  spaceAfter=2, keepWithNext=True)
sSubT  = ParagraphStyle('SubT',     fontName='Helvetica-Bold',    fontSize=11,   leading=15, textColor=TEAL, spaceAfter=3,  spaceBefore=8, keepWithNext=True)
sBul   = ParagraphStyle('Bul',      fontName='Helvetica',         fontSize=10.5, leading=17, textColor=DARK, spaceAfter=4,  leftIndent=14, alignment=TA_JUSTIFY)
sHdr   = ParagraphStyle('Hdr',      fontName='Helvetica',         fontSize=8.5,  leading=12, textColor=GMID)
sLvlG  = ParagraphStyle('LvlG',     fontName='Helvetica-Bold',    fontSize=11,   leading=15, textColor=MAG,  spaceAfter=2,  spaceBefore=6, keepWithNext=True)
sLvlS  = ParagraphStyle('LvlS',     fontName='Helvetica-Bold',    fontSize=10.5, leading=15, textColor=TEAL, spaceAfter=1,  spaceBefore=4, keepWithNext=True)
sLvlB  = ParagraphStyle('LvlB',     fontName='Helvetica',         fontSize=10.5, leading=17, textColor=DARK, spaceAfter=4,  leftIndent=10, alignment=TA_JUSTIFY)
sFable = ParagraphStyle('Fable',    fontName='Helvetica-Oblique', fontSize=10.5, leading=18, textColor=DARK, spaceAfter=8,  leftIndent=14, rightIndent=14, alignment=TA_JUSTIFY)
sTB    = ParagraphStyle('TB',       fontName='Helvetica-Bold',    fontSize=10.5, leading=16, textColor=TEAL, spaceAfter=1, keepWithNext=True)


# ══════════════════════════════════════════════════════════════════════════
# FLOWABLES
# ══════════════════════════════════════════════════════════════════════════
class SecLine(Flowable):
    def wrap(self, aw, ah): return (aw, 3)
    def draw(self):
        self.canv.setStrokeColor(MAG); self.canv.setLineWidth(1.4)
        self.canv.line(0, 1.5, TW, 1.5)


class QuoteBox(Flowable):
    def __init__(self, text):
        super().__init__(); self.text = text
        self._st = ParagraphStyle('QB', fontName='Helvetica-Oblique', fontSize=10.5, leading=17, textColor=DARK, alignment=TA_JUSTIFY)
    def wrap(self, aw, ah):
        self._w = aw
        _, h = Paragraph(self.text, self._st).wrap(aw-30, 9999)
        self._h = h+24; return (aw, self._h)
    def draw(self):
        c = self.canv
        c.setFillColor(TBOX); c.roundRect(0,0,self._w,self._h,4,fill=1,stroke=0)
        c.setFillColor(TEAL); c.rect(0,0,4,self._h,fill=1,stroke=0)
        p = Paragraph(self.text, self._st); p.wrap(self._w-30, self._h); p.drawOn(c,16,10)


class InfoBox(Flowable):
    def __init__(self, text):
        super().__init__(); self.text = text
        self._st = ParagraphStyle('IB', fontName='Helvetica', fontSize=10.5, leading=17, textColor=DARK, alignment=TA_JUSTIFY)
    def wrap(self, aw, ah):
        self._w = aw
        _, h = Paragraph(self.text, self._st).wrap(aw-30, 9999)
        self._h = h+24; return (aw, self._h)
    def draw(self):
        c = self.canv
        c.setFillColor(MBOX); c.roundRect(0,0,self._w,self._h,4,fill=1,stroke=0)
        c.setFillColor(MAG); c.rect(0,0,4,self._h,fill=1,stroke=0)
        p = Paragraph(self.text, self._st); p.wrap(self._w-30, self._h); p.drawOn(c,16,10)


class FBBox(Flowable):
    def __init__(self, title, items):
        super().__init__(); self.title=title; self.items=items
        self._tst = ParagraphStyle('FBT', fontName='Helvetica-Bold',   fontSize=10.5, leading=15, textColor=TEAL)
        self._ist = ParagraphStyle('FBI', fontName='Helvetica',         fontSize=10.5, leading=16, textColor=DARK, alignment=TA_JUSTIFY)
        self._lst = ParagraphStyle('FBL', fontName='Helvetica-Bold',    fontSize=10.5, leading=16, textColor=MAG,  alignment=TA_JUSTIFY)
    def wrap(self, aw, ah):
        self._w=aw
        _, th = Paragraph(self.title, self._tst).wrap(aw-28, 9999)
        h = th+26
        for i,it in enumerate(self.items):
            st = self._lst if i==len(self.items)-1 else self._ist
            _, ih = Paragraph(f'• {it}', st).wrap(aw-40, 9999)
            h += ih+7
        self._h=h; return (aw, self._h)
    def draw(self):
        c=self.canv
        c.setFillColor(TBOX); c.roundRect(0,0,self._w,self._h,4,fill=1,stroke=0)
        c.setStrokeColor(TEAL); c.setLineWidth(0.5)
        c.roundRect(0,0,self._w,self._h,4,fill=0,stroke=1)
        y=self._h-14
        tp=Paragraph(self.title,self._tst); _,th=tp.wrap(self._w-28,9999)
        y-=th; tp.drawOn(c,14,y); y-=12
        for i,it in enumerate(self.items):
            st=self._lst if i==len(self.items)-1 else self._ist
            ip=Paragraph(f'• {it}',st); _,ih=ip.wrap(self._w-40,9999)
            y-=ih; ip.drawOn(c,20,y); y-=7


class DualGrid(Flowable):
    def __init__(self, h1, h2, c1, c2, hcolor=None):
        super().__init__()
        self.h1,self.h2=h1,h2; self.c1,self.c2=c1,c2
        self.hcolor=hcolor or MAG; self.RH=30
    def wrap(self, aw, ah):
        self._w=aw; self._h=36+max(len(self.c1),len(self.c2))*self.RH
        return (self._w, self._h)
    def draw(self):
        c=self.canv; cw=self._w/2; n=max(len(self.c1),len(self.c2)); H=36+n*self.RH
        c.setFillColor(self.hcolor); c.rect(0,H-36,self._w,36,fill=1,stroke=0)
        c.setFillColor(WHITE); c.setFont('Helvetica-Bold',10.5)
        c.drawCentredString(cw/2,H-20,self.h1); c.drawCentredString(cw+cw/2,H-20,self.h2)
        c.setStrokeColor(GLIN); c.setLineWidth(0.4); c.line(cw,0,cw,H-36)
        for i in range(n):
            y=H-36-(i+1)*self.RH
            if i%2==0: c.setFillColor(GLT); c.rect(0,y,self._w,self.RH,fill=1,stroke=0)
            for val,cx in [(self.c1[i] if i<len(self.c1) else '',cw/2),
                           (self.c2[i] if i<len(self.c2) else '',cw+cw/2)]:
                c.setFillColor(DARK); c.setFont('Helvetica',10)
                words=val.split(); lines=[]; cur=''
                for w in words:
                    t=(cur+' '+w).strip()
                    if c.stringWidth(t,'Helvetica',10)<cw-18: cur=t
                    else: lines.append(cur); cur=w
                lines.append(cur)
                lh=13; sy=y+(self.RH-len(lines)*lh)/2+(len(lines)-1)*lh
                for li,ln in enumerate(lines): c.drawCentredString(cx,sy-li*lh,ln)
        c.setStrokeColor(GLIN); c.setLineWidth(0.5); c.rect(0,0,self._w,H,fill=0,stroke=1)


class FableBox(Flowable):
    """Caixa lavanda com borda magenta para a Fábula.
    Suporta split() do ReportLab: se não couber numa página, divide
    os parágrafos entre páginas, mantendo a borda em cada parte."""

    def __init__(self, paras, author=''):
        super().__init__()
        self.paras  = paras
        self.author = author
        self._st  = ParagraphStyle('FBx', fontName='Helvetica-Oblique',
                                   fontSize=10.5, leading=18, textColor=DARK,
                                   spaceAfter=8, leftIndent=4, rightIndent=4,
                                   alignment=TA_JUSTIFY)
        self._ast = ParagraphStyle('FAu', fontName='Helvetica-Oblique',
                                   fontSize=9.5, textColor=GMID, alignment=TA_RIGHT)
        self._PAD = 16   # padding interno horizontal
        self._VPD = 12   # padding vertical topo/base

    def _para_heights(self, avail_w):
        """Retorna lista de alturas de cada parágrafo na largura disponível."""
        inner = avail_w - 2 * self._PAD
        heights = []
        for par in self.paras:
            _, h = Paragraph(par, self._st).wrap(inner, 9999)
            heights.append(h + 8)   # +8 = spaceAfter
        return heights

    def wrap(self, aw, ah):
        self._w = aw
        heights  = self._para_heights(aw)
        inner    = aw - 2 * self._PAD
        _, ath   = Paragraph(self.author, self._ast).wrap(inner, 9999)
        self._h  = self._VPD + sum(heights) + ath + self._VPD
        return (aw, self._h)

    def split(self, aw, ah):
        """Divide os parágrafos entre duas FableBox se necessário."""
        heights = self._para_heights(aw)
        inner   = aw - 2 * self._PAD
        _, ath  = Paragraph(self.author, self._ast).wrap(inner, 9999)

        disponivel = ah - 2 * self._VPD - ath - 8
        if disponivel <= 0:
            return []   # não cabe nada — ReportLab tentará nova página

        acum  = 0
        corte = 0
        for i, h in enumerate(heights):
            if acum + h > disponivel:
                break
            acum += h
            corte = i + 1

        if corte == 0:
            return []   # nem o primeiro parágrafo cabe

        if corte >= len(self.paras):
            return [self]   # cabe tudo

        # Parte 1: parágrafos [0, corte) — sem autoria
        parte1 = FableBox(self.paras[:corte], author='')
        # Parte 2: parágrafos [corte, fim) — com autoria
        parte2 = FableBox(self.paras[corte:], author=self.author)
        return [parte1, parte2]

    def draw(self):
        c   = self.canv
        w, h = self._w, self._h
        # Fundo lavanda + borda magenta
        c.setFillColor(HexColor('#F3EEFB'))
        c.roundRect(0, 0, w, h, 6, fill=1, stroke=0)
        c.setStrokeColor(MAG)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 6, fill=0, stroke=1)
        # Parágrafos
        y = h - self._VPD
        for par in self.paras:
            pp = Paragraph(par, self._st)
            _, ph = pp.wrap(w - 2 * self._PAD, 9999)
            y -= ph
            pp.drawOn(c, self._PAD, y)
            y -= 8
        # Autoria
        if self.author:
            ap = Paragraph(self.author, self._ast)
            _, ah = ap.wrap(w - 2 * self._PAD, 9999)
            y -= ah + 4
            ap.drawOn(c, self._PAD, y)


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════
def p(t):      return Paragraph(t, sBody)
def bl(t):     return Paragraph(f'• {t}', sBul)
def sp(h=0.3): return Spacer(1, h*cm)


def pmulti(texto):
    """Divide texto por linhas em branco (\\n\\n) em múltiplos Paragraphs.
    Se não houver quebra dupla, retorna lista com 1 elemento."""
    partes = [trecho.strip() for trecho in re.split(r'\n\s*\n', texto.strip()) if trecho.strip()]
    if not partes:
        return [p('')]
    return [p(trecho) for trecho in partes]


def subsection(title, *content):
    """Subtítulo junto com APENAS o primeiro elemento. O resto flui livremente."""
    content = list(content)
    anchor = KeepTogether([sp(0.4), Paragraph(title, sSubT), sp(0.05), content[0]])
    rest = content[1:]
    return [anchor] + rest


def nivel(titulo, texto):
    return KeepTogether([
        Paragraph(f'<b>{titulo}</b>', sLvlS),
        Paragraph(texto, sLvlB),
    ])


# ══════════════════════════════════════════════════════════════════════════
# GERADOR PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════
def gerar_laudo(tipo, asa_dominante, subtipo_dom, subtipo_int, subtipo_rem,
                nome, cargo, output_path, mes_ano='Junho de 2026'):
    """
    tipo:           1-9
    asa_dominante:  número da asa dominante (deve ser uma das duas adjacentes ao tipo)
    subtipo_dom/int/rem: 'AP', '1A1' ou 'SOC' (cada um usado uma vez)
    nome, cargo:    dados do colaborador
    output_path:    caminho do PDF de saída
    """
    sec = carregar_secoes(tipo)
    nome_tipo = NOMES_TIPO[tipo]

    asa_ant, asa_seg = asas_do_tipo(tipo)
    if asa_dominante not in (asa_ant, asa_seg):
        raise ValueError(f"Asa {asa_dominante} não é adjacente ao Tipo {tipo} (esperado {asa_ant} ou {asa_seg}).")
    nome_asa = NOMES_TIPO[asa_dominante]
    texto_asa = sec.get(f'ASA_{asa_dominante}', '')

    chave_sub = chave_subtipo(subtipo_dom, subtipo_int, subtipo_rem)
    texto_subtipo = sec.get(chave_sub, '')
    label_subtipo = (f"{NOMES_SUBTIPO[subtipo_dom]} "
                     f"({LABELS_SUBTIPO_LONGO[subtipo_int]} e {LABELS_SUBTIPO_LONGO[subtipo_rem]} reprimidos)")

    HDR = f'| {nome}  |  {cargo} |'

    # ── Page templates ──────────────────────────────────────────────────
    FOOTER_COLOR = HexColor('#7B1D6B')  # mesma cor do canto da capa

    def footer_mag(c):
        c.setFillColor(FOOTER_COLOR); c.rect(0,0,PW,1.4*cm,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',6.5); c.setFillColor(WHITE)
        c.drawCentredString(PW/2,0.85*cm,'TESTE DE PERFIL COMPORTAMENTAL COM BASE NA PERSONALIDADE – 9&SELF')
        c.drawCentredString(PW/2,0.50*cm,'DESENVOLVIDO POR LÚCIA KRATZ E RYUZA GONÇALVES')

    def cover_cb(c, doc):
        c.saveState()
        # Degradê diagonal (canto superior-esq escuro -> inferior-dir magenta)
        c1 = HexColor('#26093F')  # roxo bem escuro (topo-esquerda)
        c2 = HexColor('#4D2971')  # roxo médio (meio)
        c3 = HexColor('#7B1D6B')  # magenta (canto inferior-direita)
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

        # Manchas orgânicas translúcidas (gradientes radiales simulados com círculos concêntricos)
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
        mancha(PW*0.15, PH*0.85, 6*cm, (0.35, 0.15, 0.55), 0.07)
        c.restoreState()

        c.saveState()
        c.setFont('Helvetica-Bold',6.5); c.setFillColorRGB(1,1,1,alpha=0.7)
        c.drawCentredString(PW/2,0.85*cm,'TESTE DE PERFIL COMPORTAMENTAL COM BASE NA PERSONALIDADE – 9&SELF')
        c.drawCentredString(PW/2,0.50*cm,'DESENVOLVIDO POR LÚCIA KRATZ E RYUZA GONÇALVES')
        c.setFont('Helvetica',8)
        c.drawRightString(PW-1.5*cm,0.55*cm,'1')
        c.restoreState()

    def inner_cb(c, doc):
        c.saveState()
        c.setStrokeColor(GLIN); c.setLineWidth(0.4)
        c.line(ML,PH-1.8*cm,PW-MR,PH-1.8*cm)
        c.setFont('Helvetica',8.5); c.setFillColor(GMID)
        c.drawString(ML,PH-1.55*cm,HDR)
        footer_mag(c)
        c.setFont('Helvetica',8); c.setFillColor(WHITE)
        c.drawRightString(PW-1.5*cm,0.55*cm,str(doc.page))
        c.restoreState()

    def hdr():
        return Paragraph(HDR, sHdr)

    frame_cover = Frame(ML,MB,TW,PH-MB-0.5*cm,id='cover')
    frame_inner = Frame(ML,MB,TW,PH-MB-2.2*cm,id='inner')
    pt_cover = PageTemplate(id='Cover',frames=[frame_cover],onPage=cover_cb)
    pt_inner = PageTemplate(id='Inner',frames=[frame_inner],onPage=inner_cb)
    doc = BaseDocTemplate(output_path, pagesize=A4, pageTemplates=[pt_cover,pt_inner])

    story = []

    # ══════════════════════════════════════════════════ CAPA
    LAVANDA   = HexColor('#D9C7F5')
    BRANCO_SF = HexColor('#FFFFFF')
    CINZA_SF  = HexColor('#E4D9F7')

    story += [
        sp(3.6),
        Paragraph('9&amp;Self',
            ParagraphStyle('Logo', fontName=LOGO_FONT, fontSize=50, leading=56, textColor=LAVANDA, alignment=1)),
        sp(0.6),
        Paragraph('Relatório Eneagrama',
            ParagraphStyle('CT', fontName='Helvetica-Bold', fontSize=26, textColor=BRANCO_SF, alignment=1, spaceAfter=0)),
        sp(1.2),
        Paragraph(nome,
            ParagraphStyle('CN', fontName='Helvetica', fontSize=16, textColor=LAVANDA, alignment=1)),
        sp(0.6),
        HRFlowable(width='55%', color=BRANCO_SF, thickness=1.5, spaceAfter=0),
        sp(0.6),
        Paragraph(f'<b>Cargo:</b> {cargo}',
            ParagraphStyle('CC', fontName='Helvetica', fontSize=12, textColor=BRANCO_SF, alignment=1, spaceAfter=4)),
        Paragraph(mes_ano,
            ParagraphStyle('CD', fontName='Helvetica', fontSize=12, textColor=BRANCO_SF, alignment=1)),
        sp(3.0),
    ]
    GLASS_BG = HexColor('#FFFFFF')
    for lbl, val in [
        (f'Eneatipo {tipo}:', nome_tipo),
        (f'Asa {asa_dominante}:', nome_asa),
        ('Subtipo:', label_subtipo),
    ]:
        t = Table([[
            Paragraph(f'<b>{lbl}</b>', ParagraphStyle('RL',fontName='Helvetica-Bold',fontSize=10.5,textColor=HexColor('#3A1F5C'))),
            Paragraph(val, ParagraphStyle('RV',fontName='Helvetica',fontSize=10.5,textColor=HexColor('#3A1F5C'))),
        ]], colWidths=[3*cm,TW-3*cm])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),GLASS_BG),('LINEBEFORE',(0,0),(0,-1),3.5,MAG),
            ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),
            ('LEFTPADDING',(0,0),(-1,-1),12)]))
        story += [t, sp(0.15)]
    story += [NextPageTemplate('Inner'), PageBreak()]

    # ══════════════════════════════════════════════════ INTRODUÇÃO
    story.append(KeepTogether([
        Paragraph('Introdução', sSecT), SecLine(), sp(0.15),
        p('O <b>9&Self</b> é um instrumento de identificação de características pessoais e profissionais '
          'desenvolvido pelas especialistas <b>Dra. Lúcia Kratz</b> e <b>Ryuza Gonçalves</b>. '
          'O teste fundamenta-se nos traços de personalidade do Eneagrama — a partir dos estudos '
          'pioneiros de George Ivanovich Gurdjieff, Helen Palmer, David Daniels, Claudio Naranjo, '
          'Don Richards Riso e Russ Hudson —, aliados à teoria junguiana dos traços psicológicos e '
          'complementados pela Teoria das Necessidades Adquiridas de McClelland e pelo Coaching Executivo.'),
    ]))
    story += [
        p('Dentro desses estudos, identificam-se <b>9 tipos básicos de personalidade</b> que se subdividem '
          'em <b>216 padrões diferentes de comportamento</b>. Os nove tipos básicos são: <b>Perfeição e '
          'Excelência, Prestativo e Relacional, Performance e Imagem, Autêntico e Profundo, Observador e '
          'Privacidade, Precavido e Questionador, Visionário e Otimista, Desafiador e Controlador, '
          'Harmônico e Diplomático.</b>'),
        p('Um dos objetivos do 9&Self é oferecer demonstrações e argumentos que facilitam o caminho para '
          'maior respeito e tolerância consigo mesmo e com os outros, auxiliando na apreciação de dons, '
          'talentos e competências. Compreender a própria tipologia de personalidade provoca uma '
          'transformação favorável na vida das pessoas em uma grande variedade de situações pessoais e profissionais.'),
        p('O comportamento das pessoas é bastante variado, mas segue alguns padrões — modelos nos quais '
          'os indivíduos preferem observar o mundo e fazer julgamentos. As tipologias de personalidade '
          'são profundas e estruturantes no caráter de cada indivíduo. Não podemos alterar a base da '
          'nossa personalidade, mas podemos desenvolvê-la e ganhar maturidade.'),
        p('O <b>9&Self</b> está organized da seguinte forma:'),
    ]
    for item in ['<b>Tipologia da Personalidade</b>','<b>Subtipo da Personalidade</b>',
                 '<b>Influência das Personalidades</b>','<b>Interação Social</b>',
                 'Estilo de Trabalho','Ambiente de Trabalho','Estresse da Personalidade',
                 'Comunicação e Feedback','Tendências na Liderança','Motivação',
                 'Desenvolvimento e Evolução da Personalidade','Relacionamentos','Fábula']:
        story.append(bl(item))

    # ══════════════════════════════════════════════════ TIPOLOGIA
    story.append(PageBreak())
    tip_paras = pmulti(sec.get('TIPOLOGIA', ''))
    # Parágrafo de voz (1ª pessoa): detectado por aspas iniciais
    def is_voz(txt):
        return txt.strip().startswith('"') or txt.strip().startswith('\u201c')

    story.append(KeepTogether([
        Paragraph('Tipologia da Personalidade', sSecT), SecLine(), sp(0.15),
        tip_paras[0],
    ]))
    for paragrafo in tip_paras[1:]:
        txt_raw = paragrafo.text if hasattr(paragrafo, 'text') else ''
        if is_voz(txt_raw):
            story.append(sp(0.15))
            story.append(QuoteBox(txt_raw))
        else:
            story.append(paragrafo)

    # Caixa de aviso filosófico (igual para todos os tipos)
    story.append(sp(0.3))
    AVISO_FILOSOFIA = (
        '<b>⚠ ATENÇÃO: A JORNADA DO AUTOCONHECIMENTO</b><br/><br/>'
        'Na filosofia do Eneagrama, não existe personalidade melhor ou pior. Este laudo não é um '
        'rótulo, mas um mapa para o seu autodesenvolvimento. As respostas refletem a sua '
        'autopercepção atual; a personalidade é o ponto de partida, mas a consciência de si se '
        'fortalece com a terapia and a vivência. O laudo é apenas um recorte do seu momento '
        'presente. Se, após o seu processo de expansão, perceber que sua autopercepção mudou, '
        'sinta-se à vontade para refazer o teste após um período de reflexão. Acolha o seu '
        'processo e veja o laudo como um companheiro de caminhada.'
    )
    story.append(InfoBox(AVISO_FILOSOFIA))

    # ── IMAGEM: Dinâmica de Evolução/Involução do tipo ──
    img_evolucao = imagem_tipo(tipo, sufixo='b')
    if img_evolucao:
        story.append(sp(0.3))
        story.append(Paragraph(
            f'A imagem abaixo representa visualmente o tipo <b>{nome_tipo}</b> e suas dinâmicas '
            f'de evolução e involução — ou seja, os caminhos de crescimento e de estresse que '
            f'esse perfil pode percorrer ao longo da vida.',
            ParagraphStyle('ImgCaption', fontName='Helvetica', fontSize=10, leading=14,
                            textColor=HexColor('#3A1F5C'), alignment=TA_JUSTIFY, spaceAfter=8)
        ))
        story.append(img_evolucao)

    pad_paras = pmulti(sec.get('PADRAO_INFANCIA', ''))
    story += subsection('Padrão na Infância', pad_paras[0])
    for paragrafo in pad_paras[1:]:
        story.append(paragrafo)

    # ══════════════════════════════════════════════════ PONTOS FORTES/FRACOS
    def parse_pontos(raw, label):
        """Suporta dois formatos:
        - Antigo: 'texto introdutório\\nitem1 | item2 | ...'
        - Novo:   'item1 | item2 | ...' (sem texto introdutório)
        """
        partes = raw.rsplit('\n', 1)
        if len(partes) == 2 and '|' in partes[1]:
            return partes[0].strip(), split_pipes(partes[1])
        itens = split_pipes(raw)
        if len(itens) > 1:
            return '', itens
        return raw, []

    pf_texto, pf_itens = parse_pontos(sec.get('PONTOS_FORTES', ''), 'fortes')
    pfx_texto, pfx_itens = parse_pontos(sec.get('PONTOS_FRACOS', ''), 'fracos')

    intro_pf_pfx = f'{pf_texto} {pfx_texto}'.strip()
    if not intro_pf_pfx:
        intro_pf_pfx = (
            f'Todo perfil de personalidade carrega consigo um conjunto de atributos que, quando bem '
            f'canalizados, se tornam diferenciais competitivos genuínos. Da mesma forma, existem '
            f'tendências comportamentais que, sem a devida consciência, podem limitar o desempenho '
            f'e gerar atritos nos relacionamentos pessoais e profissionais. O mapeamento abaixo '
            f'sintetiza os principais pontos de força e os pontos de atenção do perfil <b>{nome_tipo}</b>.'
        )

    def dual_list_table(h1, h2, c1, c2, hcolor=None):
        """Tabela de 2 colunas com altura automática por linha (para itens longos)."""
        hcolor = hcolor or MAG
        n = max(len(c1), len(c2))
        header_style = ParagraphStyle('DLH', fontName='Helvetica-Bold', fontSize=10.5, textColor=WHITE, alignment=1)
        cell_style = ParagraphStyle('DLC', fontName='Helvetica', fontSize=10, leading=14, textColor=DARK, alignment=TA_JUSTIFY)
        data = [[Paragraph(h1, header_style), Paragraph(h2, header_style)]]
        for i in range(n):
            v1 = c1[i] if i < len(c1) else ''
            v2 = c2[i] if i < len(c2) else ''
            data.append([Paragraph(v1, cell_style), Paragraph(v2, cell_style)])
        t = Table(data, colWidths=[TW/2, TW/2], repeatRows=1)
        style = [
            ('BACKGROUND',(0,0),(-1,0),hcolor),
            ('TOPPADDING',(0,0),(-1,0),8), ('BOTTOMPADDING',(0,0),(-1,0),8),
            ('GRID',(0,0),(-1,-1),0.4,GLIN),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),10), ('RIGHTPADDING',(0,0),(-1,-1),10),
            ('TOPPADDING',(0,1),(-1,-1),8), ('BOTTOMPADDING',(0,1),(-1,-1),8),
        ]
        for i in range(1, n+1):
            if (i-1) % 2 == 0:
                style.append(('BACKGROUND',(0,i),(-1,i),GLT))
        t.setStyle(TableStyle(style))
        return t

    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph('Pontos Fortes e Fracos da Personalidade', sSecT),
        SecLine(), sp(0.15),
        p(intro_pf_pfx),
        sp(0.2),
        dual_list_table('✓  Pontos Fortes','⚠  Pontos Fracos', pf_itens, pfx_itens),
    ]))

    # ══════════════════════════════════════════════════ SUBTIPO
    story.append(PageBreak())
    asa_niveis = split_pipes(texto_asa) if '\n' not in texto_asa else texto_asa.split('\n')
    asa_niveis = [s.strip() for s in re.split(r'(?:\r?\n)+', texto_asa) if s.strip()]

    story.append(KeepTogether([
        Paragraph('Subtipo da Personalidade', sSecT),
        SecLine(), sp(0.15),
        Paragraph(f'Influência das Personalidades | {nome_asa} |', sSubT), sp(0.05),
        p(asa_niveis[0] if asa_niveis else ''),
    ]))
    for linha in asa_niveis[1:]:
        story.append(p(linha))

    # ── IMAGEM: Tipo com Asas ──
    img_asas = imagem_tipo(tipo, sufixo='')
    if img_asas:
        story.append(sp(0.3))
        story.append(Paragraph(
            f'A imagem abaixo ilustra o tipo <b>{nome_tipo}</b> e suas asas — as influências '
            f'dos tipos vizinhos que moldam a expressão da sua personalidade.',
            ParagraphStyle('ImgCaption2', fontName='Helvetica', fontSize=10, leading=14,
                            textColor=HexColor('#3A1F5C'), alignment=TA_JUSTIFY, spaceAfter=8)
        ))
        story.append(img_asas)
        story.append(sp(0.3))

    story += subsection(
        f'Interação Social | {NOMES_SUBTIPO[subtipo_dom]} · {LABELS_SUBTIPO_LONGO[subtipo_int]} · '
        f'{LABELS_SUBTIPO_LONGO[subtipo_rem]} Reprimido |',
        p(texto_subtipo),
    )

    # ══════════════════════════════════════════════════ ESTILO DE TRABALHO
    story.append(PageBreak())
    amb_paras = pmulti(sec.get('AMBIENTE_TRABALHO', ''))
    story.append(KeepTogether([
        Paragraph('Estilo de Trabalho', sSecT), SecLine(), sp(0.15),
        Paragraph('Ambiente de Trabalho:', sSubT), sp(0.05),
        amb_paras[0],
    ]))
    for paragrafo in amb_paras[1:]:
        story.append(paragrafo)

    # ESTRESSE — separa a citação entre aspas como QuoteBox
    estresse_txt = sec.get('ESTRESSE', '')
    m = re.search(r'\(?["“]([^"”]+)["”]\)?', estresse_txt)
    if m:
        antes = estresse_txt[:m.start()].strip()
        depois = estresse_txt[m.end():].strip()
        depois = re.sub(r'^[\)\.\s]+', '', depois)
        if depois and not depois[0].isupper():
            depois = depois[0].upper() + depois[1:]
        antes = re.sub(r'\s*\($', '', antes).strip()
        citacao = m.group(1)
        if not citacao.startswith('"'):
            citacao = f'"{citacao}"'
        bloco_estresse = list(pmulti(antes)) + [sp(0.1), QuoteBox(citacao)]
        if depois:
            bloco_estresse += [sp(0.15)] + list(pmulti(depois))
        story += subsection('Estresse da Personalidade:', *bloco_estresse)
    else:
        story += subsection('Estresse da Personalidade:', *pmulti(estresse_txt))

    # COMUNICAÇÃO + DualGrid Estilo ao Falar / Linguagem Corporal
    fala_itens = split_pipes(sec.get('FALA', ''))
    corporal_itens = split_pipes(sec.get('LINGUAGEM_CORPORAL', ''))
    comunicacao_content = list(pmulti(sec.get('COMUNICACAO', '')))
    if fala_itens and corporal_itens:
        comunicacao_content += [
            sp(0.2),
            KeepTogether([
                Paragraph('Estilo de Comunicação:', sTB), sp(0.05),
                dual_list_table('🗣 Estilo ao Falar','🤝 Linguagem Corporal', fala_itens, corporal_itens, hcolor=TEAL),
            ]),
        ]
    elif corporal_itens:
        comunicacao_content += [
            sp(0.2),
            KeepTogether(
                [Paragraph('Linguagem Corporal:', sTB)] + [bl(item) for item in corporal_itens]
            ),
        ]
    story += subsection('Comunicação:', *comunicacao_content)

    # FEEDBACK: pontos cegos / filtros + diretrizes
    cegos_itens = split_pipes(sec.get('PONTOS_CEGOS', ''))
    filtros_itens = split_pipes(sec.get('FILTROS_DISTORCOES', ''))
    feedback_itens = split_pipes(sec.get('FEEDBACK_ITENS', ''))

    feedback_content = [
        p('Evite que as tendências automáticas do seu estilo no Eneagrama interfiram na sua forma de '
          'liderar e desenvolver pessoas.'),
        sp(0.15),
        KeepTogether([
            Paragraph('Pontos Cegos e Filtros:', sTB), sp(0.05),
            dual_list_table('🎯 Pontos Cegos','🔍 Filtros e Distorções', cegos_itens, filtros_itens, hcolor=TEAL),
        ]),
    ]
    if feedback_itens:
        feedback_content += [sp(0.2), FBBox('Diretrizes para o Feedback:', feedback_itens)]
    story += subsection('Feedback:', *feedback_content)

    # ══════════════════════════════════════════════════ LIDERANÇA E MOTIVAÇÃO
    aspectos_itens = split_pipes(sec.get('ASPECTOS_DESENVOLVER', ''))
    story.append(PageBreak())

    lid_block = [
        Paragraph('Liderança e Motivação', sSecT), SecLine(), sp(0.15),
        Paragraph('Tendências na Liderança:', sSubT), sp(0.05),
    ]
    lid_block += pmulti(sec.get('LIDERANCA', ''))
    if sec.get('TENDENCIAS_LIDERANCA'):
        lid_block += pmulti(sec.get('TENDENCIAS_LIDERANCA', ''))
    if aspectos_itens:
        lid_block += [Paragraph('Principais Aspectos a Desenvolver:', sSubT), sp(0.05)]
        for item in aspectos_itens:
            titulo, texto = split_titulo_texto(item)
            if titulo:
                lid_block.append(KeepTogether([Paragraph(f'<b>{titulo}</b>', sTB), p(texto)]))
            else:
                lid_block.append(p(texto))
    story.append(KeepTogether(lid_block))

    # PREOCUPAÇÕES (Correção de Omissão do Sistema)
    if sec.get('PREOCUPACOES'):
        preocupacoes_itens = split_pipes(sec.get('PREOCUPACOES', ''))
        story += subsection('Preocupações:', *[bl(item) for item in preocupacoes_itens])

    # MOTIVAÇÃO
    motivacao_itens = split_pipes(sec.get('MOTIVACAO', ''))
    story += subsection('Motivação:', *[bl(item) for item in motivacao_itens])

    # AUTODOMÍNIO — incorporado em Níveis de Saúde (Máximo/Moderado/Baixo)
    autodominio_itens = split_pipes(sec.get('AUTODOMINIO', ''))
    autodominio_textos = []
    for item in autodominio_itens:
        _, texto = split_titulo_texto(item)
        autodominio_textos.append(texto)
    while len(autodominio_textos) < 3:
        autodominio_textos.append('')

    # ══════════════════════════════════════════════════ HÁBITOS POSITIVOS
    habitos_raw = sec.get('HABITOS', '')
    story.append(PageBreak())

    habitos_block = [
        Paragraph('Crie Hábitos Positivos para sua Personalidade', sSecT),
        SecLine(), sp(0.15),
        p(f'O tipo {nome_tipo} deve desenvolver deliberadamente os seguintes hábitos saudáveis:'),
        sp(0.15),
    ]
    story.append(KeepTogether(habitos_block))

    # Renderizar hábitos: suporta || (separador de hábito), | (hábito simples) e \n\n (parágrafos)
    # Divide primeiro em parágrafos por \n\n
    blocos_habito = [b.strip() for b in re.split(r'\n\s*\n', habitos_raw.strip()) if b.strip()]
    for bloco in blocos_habito:
        # Cada bloco pode ter itens separados por || ou |
        if '||' in bloco:
            itens = [i.strip() for i in bloco.split('||') if i.strip()]
        elif '|' in bloco and ':' not in bloco[:30]:
            # Hábitos simples separados por |
            itens = [i.strip() for i in bloco.split('|') if i.strip()]
        elif '|' in bloco:
            itens = [i.strip() for i in bloco.split('|') if i.strip()]
        else:
            itens = [bloco]
        for item in itens:
            titulo, texto = split_titulo_texto(item)
            if titulo and texto:
                story.append(KeepTogether([
                    Paragraph(f'<b>{titulo}:</b>', sTB),
                    sp(0.05),
                    p(texto),
                    sp(0.1),
                ]))
            else:
                # Parágrafo simples (ex: "Boas Práticas e Tarefas Concretas:" ou item de lista)
                txt = (titulo or '') + (texto or '')
                if txt.startswith('•') or txt.startswith('-'):
                    story.append(bl(txt.lstrip('•- ').strip()))
                else:
                    story.append(p(txt))
                story.append(sp(0.08))

    # FRASES COMUNS
    frases_itens = split_pipes(sec.get('FRASES_COMUNS', ''))
    story += subsection('Frases Comuns:', *[bl(item) for item in frases_itens])

    # ══════════════════════════════════════════════════ NÍVEIS DE SAÚDE
    niveis_itens = split_pipes(sec.get('NIVEIS_SAUDE', ''))
    niveis_pares = []
    if len(niveis_itens) == 9:
        # Novo formato: cada item é "Título: texto completo"
        for item in niveis_itens:
            titulo_raw, texto = split_titulo_texto(item, sep=':')
            titulo_raw = (titulo_raw or '').rstrip(':').strip()
            niveis_pares.append((titulo_raw, texto))
    else:
        # Formato antigo: [titulo1, texto1, titulo2, texto2, ...]
        for i in range(0, len(niveis_itens) - 1, 2):
            titulo_raw = re.sub(r'^N\d+:\s*', '', niveis_itens[i]).strip()
            niveis_pares.append((titulo_raw, niveis_itens[i+1]))

    story.append(PageBreak())
    health_block = [
        Paragraph('Níveis de Saúde da Personalidade', sSecT),
        SecLine(), sp(0.15),
        p(f'A personalidade é dinâmica e se move ao longo de <b>9 níveis de desenvolvimento e maturidade '
          f'individual</b>. Vale ressaltar que pressões e fatores externos podem alterar temporariamente '
          f'esse níveis no tipo {nome_tipo}.'),
        sp(0.2),
        Paragraph('a) Nível Saudável (Elevado)', sLvlG),
    ]
    if autodominio_textos[0]:
        health_block.append(p(autodominio_textos[0]))
    if len(niveis_pares) > 0:
        titulo, texto = niveis_pares[0]
        health_block.append(nivel(f'Nível 1 - {titulo}', texto))
    story.append(KeepTogether(health_block))

    grupos = {3: 'b) Nível Médio', 6: 'c) Nível Não Saudável'}
    autodominio_por_grupo = {3: autodominio_textos[1], 6: autodominio_textos[2]}
    for idx in range(1, min(len(niveis_pares), 9)):
        if idx in grupos:
            cabecalho_grupo = [Paragraph(grupos[idx], sLvlG)]
            if autodominio_por_grupo.get(idx):
                cabecalho_grupo.append(p(autodominio_por_grupo[idx]))
            story.append(KeepTogether(cabecalho_grupo))
        titulo, texto = niveis_pares[idx]
        story.append(nivel(f'Nível {idx+1} - {titulo}', texto))

    # ══════════════════════════════════════════════════ DESENVOLVIMENTO (conceitual + específico)
    P1_DESENV = ('O verdadeiro processo de autodesenvolvimento não consiste em moldar uma nova '
         'personalidade ou em tentar se encaixar in um ideal de perfeição inalcançável. '
         'Pelo contrário, trata-se de um profundo e corajoso movimento de desconstrução. '
         'A personalidade que manifestamos no dia a dia nada mais é do que uma armadura de '
         'sobrevivência, uma estratégia psíquica refinada que aprendemos a estruturar ainda '
         'na infância para garantir afeto, segurança e pertencimento no mundo. Ao longo dos '
         'anos, passamos a confundir quem nós realmente somos com o peso dessa engrenagem '
         'defensiva. O ecossistema 9&Self nasce justamente para iluminar essas barreiras '
         'invisíveis, oferecendo a lucidez necessária para que você possa liderar a si mesmo '
         'com maestria, integridade e clareza de propósito.')
    P2_DESENV = ('Evoluir exige, fundamentalmente, aprender a tolerar o desconforto de se enxergar '
         'sem masks. Quando tomamos consciência dos nossos automatismos, dos nossos filtros '
         'mentais e dos gatilhos que disparam as nossas reações automáticas de estresse, '
         'deixamos de ser reféns da nossa reatividade e passamos a habitar o lugar da escolha '
         'consciente. O autodesenvolvimento legítimo não anula as suas características natas; '
         'ele flexibiliza as suas defesas. Ele permite que o realizador acesse a '
         'vulnerabilidade, que o planejador encontre a coragem, que o cuidador respeite os '
         'próprios limites e que o estrategista aprecie o valor da pausa. É um convite para '
         'sair da periferia do comportamento mecânico e assumir a centralidade da sua própria '
         'existência.')
    P3_DESENV = ('A jornada de transformação andragógica proposta neste laudo é um mapa dinâmico '
         'para o transbordo pessoal e profissional. O crescimento sustentável não acontece '
         'por meio de grandes saltos heroicos isolados, mas sim na consistência das pequenas '
         'escolhas diárias e na vigilância amorosa sobre os nossos pontos cegos. Ao abraçar '
         'este caminho, você não apenas potencializa a sua performance e a sua inteligência '
         'relacional, mas também constrói um espaço interno de paz e autonomia. Lembre-se de '
         'que a sua personalidade é apenas o ponto de partida, o canal por onde você se '
         'comunica com o ecossistema à sua volta. O seu verdadeiro eu, contudo, reside na '
         'sua capacidade de transcender esse mecanismo, transformando o conhecimento adquirido '
         'em sabedoria prática e em liderança inspiradora para a vida.')

    sTitDC = ParagraphStyle('TitDC', fontName='Helvetica-Bold', fontSize=14,
                            leading=20, textColor=MAG, alignment=1,
                            spaceAfter=14, spaceBefore=4)

    # Texto específico do tipo (da tag DESENVOLVIMENTO)
    dev_paras = pmulti(sec.get('DESENVOLVIMENTO', ''))

    # Tudo em PageBreak único — título + conceitual + específico + infobox
    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph('O Despertar da Consciência: O Caminho do Autodesenvolvimento', sTitDC),
        SecLine(), sp(0.25),
        p(P1_DESENV),
    ]))
    story.append(sp(0.2))
    story.append(p(P2_DESENV))
    story.append(sp(0.2))
    story.append(p(P3_DESENV))
    story.append(sp(0.3))
    # Texto específico do tipo flui continuamente
    for paragrafo in dev_paras:
        story.append(paragrafo)
        story.append(sp(0.15))
    if sec.get('INFOBOX_DESENVOLVIMENTO'):
        story.append(InfoBox(sec.get('INFOBOX_DESENVOLVIMENTO', '')))

    # ══════════════════════════════════════════════════ RELACIONAMENTOS
    if sec.get('RELACIONAMENTOS'):
        story.append(PageBreak())
        story.append(KeepTogether([
            Paragraph('Seus Relacionamentos: Como Você Interage com Outros Perfis', sSecT),
            SecLine(), sp(0.15)
        ]))

        def gerar_linhas_escrita(num_linhas=6):
            rows = [['']] * num_linhas
            t = Table(rows, colWidths=[TW], rowHeights=[18]*num_linhas)
            t.setStyle(TableStyle([
                ('LINEBELOW', (0,0), (-1,-1), 0.5, HexColor('#CCCCCC')),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ]))
            return t

        sRelHeader = ParagraphStyle('RelHeader', fontName='Helvetica-Bold', fontSize=11.5,
                                     leading=16, textColor=MAG, spaceBefore=14, spaceAfter=4)

        # Trabalha direto no texto raw (pmulti normaliza \n simples em espaço,
        # então o parsing precisa ser feito ANTES de criar os Paragraphs)
        raw_rel = sec.get('RELACIONAMENTOS', '')
        blocos_raw = [t.strip() for t in re.split(r'\n\s*\n', raw_rel.strip()) if t.strip()]

        for bloco_txt in blocos_raw:
            if re.match(r'^\s*•?\s*Com (o|outro)\s', bloco_txt):
                # Bloco de compatibilidade: "• Com o perfil X — Y\n- Como a dupla funciona: ...\n- Exemplo...\n..."
                linhas = [l.strip() for l in bloco_txt.split('\n') if l.strip()]
                titulo_limpo = re.sub(r'^\s*•\s*', '', linhas[0])
                story.append(Paragraph(f'★ {titulo_limpo}', sRelHeader))
                for sub in linhas[1:]:
                    sub_limpo = re.sub(r'^-\s*', '', sub)
                    story.append(p(sub_limpo))
                    story.append(sp(0.08))
                if '✍️' in bloco_txt:
                    story.append(sp(0.1))
                    story.append(gerar_linhas_escrita(6))
                    story.append(sp(0.2))
            elif bloco_txt.startswith('Seu Espaço de Prática'):
                # Subtítulo de nova subseção
                story.append(sp(0.3))
                story.append(Paragraph(bloco_txt, sSubT))
                story.append(sp(0.1))
            elif bloco_txt.startswith('*') and bloco_txt.endswith('*'):
                # Texto introdutório em itálico, ex: "*Use este laboratório...*"
                texto_italico = bloco_txt.strip('*').strip()
                story.append(Paragraph(f'<i>{texto_italico}</i>', sBody))
            elif re.match(r'^\d+\.\s', bloco_txt):
                # Pergunta numerada de reflexão — recebe linhas para escrita manual
                story.append(p(bloco_txt))
                story.append(sp(0.1))
                story.append(gerar_linhas_escrita(4))
                story.append(sp(0.2))
            else:
                story.append(p(bloco_txt))

    # ══════════════════════════════════════════════════ FÁBULA
    fabula_txt = sec.get('FABULA', '')
    fabula_corpo = fabula_txt
    fabula_titulo = f'A Fábula do {nome_tipo}'
    if ':' in fabula_txt[:40]:
        possivel_titulo, _, resto = fabula_txt.partition(':')
        # Só trata como título se for curto (nome próprio, não a frase inteira)
        if len(possivel_titulo) < 30:
            fabula_titulo = possivel_titulo.strip()
            fabula_corpo = resto.strip()

    if '\n\n' in fabula_corpo or '\n \n' in fabula_corpo:
        paras_finais = [t.strip() for t in re.split(r'\n\s*\n', fabula_corpo.strip()) if t.strip()]
    else:
        paragrafos_fabula = [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-ZÀ-Ú])', fabula_corpo) if s.strip()]
        # Agrupa frases em parágrafos de tamanho razoável (~2-3 frases cada)
        paras_finais = []
        buf = []
        for frase in paragrafos_fabula:
            buf.append(frase)
            if sum(len(x) for x in buf) > 220:
                paras_finais.append(' '.join(buf))
                buf = []
        if buf:
            paras_finais.append(' '.join(buf))

    story.append(PageBreak())
    titulo_fabula_par = Paragraph(fabula_titulo,
        ParagraphStyle('FT',fontName='Helvetica-Bold',fontSize=17,textColor=MAG,
                       alignment=1,spaceAfter=12,spaceBefore=4))
    story.append(KeepTogether([
        Paragraph('Fábula', sSecT), SecLine(), sp(0.15),
        sp(0.2), titulo_fabula_par,
    ]))
    # Um único FableBox — o split() cuida da quebra de página se necessário
    story.append(FableBox(paras_finais, 'Autor Desconhecido'))

    # PERGUNTAS DA FÁBULA
    perguntas_txt = sec.get('PERGUNTAS_FABULA', '').strip()
    if perguntas_txt:
        perguntas = split_pipes(perguntas_txt)
        story.append(sp(0.3))
        story.append(KeepTogether([
            Paragraph('Reflexões sobre a Fábula', sSubT), sp(0.1),
        ]))
        # Estilo das perguntas
        sPerq = ParagraphStyle('Perq', fontName='Helvetica-Bold', fontSize=10,
                               leading=15, textColor=DARK, spaceBefore=10, spaceAfter=4)
        # Linhas pontilhadas para escrita manual
        def linha_resposta():
            """Retorna uma tabela com 4 linhas cinza-claras para escrita manual."""
            rows = [['']] * 4
            t = Table(rows, colWidths=[TW], rowHeights=[18]*4)
            t.setStyle(TableStyle([
                ('LINEBELOW', (0,0), (-1,-1), 0.5, HexColor('#CCCCCC')),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ]))
            return t
        for idx, pergunta in enumerate(perguntas, 1):
            story.append(Paragraph(f'{idx}. {pergunta}', sPerq))
            story.append(sp(0.05))
            story.append(linha_resposta())
            story.append(sp(0.15))

    # PLAYLIST
    playlist_txt = sec.get('PLAYLIST', '').strip()
    musicas = split_pipes(playlist_txt)
    is_link = playlist_txt.lower().startswith('link') or 'http' in playlist_txt.lower()

    if is_link:
        playlist_conteudo = Table([[Paragraph(
            re.sub(r'^(Link da Playlist[^:]*:)', r'<b>\1</b>\n', playlist_txt),
            ParagraphStyle('LK',fontName='Helvetica',fontSize=10,textColor=TEAL,leading=16,alignment=1))
        ]], colWidths=[TW], style=TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),TBOX),('LINEBEFORE',(0,0),(0,-1),3,TEAL),
            ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),
            ('LEFTPADDING',(0,0),(-1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),16),
        ]))
        playlist_intro = ('Se desejar assistir a vídeos detalhados sobre o seu perfil, basta acessar o endereço '
            'eletrônico abaixo para acompanhar uma seleção de conteúdos preparados sobre a sua '
            'personalidade. Recomenda-se iniciar a partir do vídeo 3 desta lista de reprodução.')
    else:
        linhas_musicas = ''.join(f'• {m}<br/>' for m in musicas).rstrip('<br/>')
        playlist_conteudo = Table([[Paragraph(
            linhas_musicas,
            ParagraphStyle('LK',fontName='Helvetica',fontSize=10,textColor=TEAL,leading=18,alignment=0))
        ]], colWidths=[TW], style=TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),TBOX),('LINEBEFORE',(0,0),(0,-1),3,TEAL),
            ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),
            ('LEFTPADDING',(0,0),(-1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),16),
        ]))
        playlist_intro = ('Esta é uma seleção musical que reflete os temas, emoções e jornada de '
            'desenvolvimento da sua personalidade. Recomenda-se ouvir com atenção às letras e melodias.')

    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph('Playlist da Personalidade', sSecT), SecLine(), sp(0.15),
        p(playlist_intro),
        sp(0.15),
        playlist_conteudo,
    ]))

    # ══════════════════════════════════════════════════ ASSINATURA DIGITAL
    agora_utc = datetime.now(timezone.utc)
    data_hora_fmt = agora_utc.strftime('%d/%m/%Y %H:%M:%S UTC')
    hash_uuid = str(uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f'{nome}-{tipo}-{asa_dominante}-{subtipo_dom}{subtipo_int}{subtipo_rem}-{agora_utc.isoformat()}'
    )).upper()

    sSeloTitulo = ParagraphStyle('SeloTitulo', fontName='Helvetica-Bold', fontSize=12,
                                  textColor=HexColor('#1A9460'), alignment=0, spaceAfter=10)
    sSeloLabel  = ParagraphStyle('SeloLabel', fontName='Helvetica-Bold', fontSize=9.5,
                                  textColor=DARK, alignment=0, leading=13)
    sSeloValor  = ParagraphStyle('SeloValor', fontName='Helvetica', fontSize=9.5,
                                  textColor=DARK, alignment=0, leading=13)
    sSeloRodape = ParagraphStyle('SeloRodape', fontName='Helvetica', fontSize=9,
                                  textColor=HexColor('#666666'), alignment=0, spaceBefore=10)

    selo_tabela = Table([
        [Paragraph('Aprovador:', sSeloLabel),          Paragraph('Dra. Lucia Kratz', sSeloValor)],
        [Paragraph('Registro Profissional:', sSeloLabel), Paragraph('CRP 09/20590', sSeloValor)],
        [Paragraph('Data e Hora (UTC):', sSeloLabel),  Paragraph(data_hora_fmt, sSeloValor)],
        [Paragraph('Hash UUID de Validação:', sSeloLabel), Paragraph(hash_uuid, sSeloValor)],
    ], colWidths=[5.5*cm, 8*cm])
    selo_tabela.hAlign = 'LEFT'
    selo_tabela.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (0,-1), 10),
    ]))

    story.append(sp(1.0))
    story.append(KeepTogether([
        Paragraph('✓ DOCUMENTO ASSINADO ELETRONICAMENTE', sSeloTitulo),
        selo_tabela,
        Paragraph(
            'Este registro é gerado de forma automatizada e serve como validação de '
            'autenticidade e autoria técnica deste laudo, elaborado com base nos critérios '
            'metodológicos do sistema 9&Self.',
            sSeloRodape
        ),
        sp(0.4),
        Paragraph(
            'Doutora em Psicologia · Especialista TCC, Neuromodulação e Musicoterapia · Goiânia, GO',
            ParagraphStyle('AssInfo2', fontName='Helvetica', fontSize=9,
                            textColor=DARK, alignment=0, leading=14)
        ),
    ]))

    doc.build(story)
    return output_path


if __name__ == '__main__':
    out = gerar_laudo(
        tipo=1, asa_dominante=2,
        subtipo_dom='AP', subtipo_int='1A1', subtipo_rem='SOC',
        nome='Fabiano de Sousa Vaz de Campos',
        cargo='Diretor - CIRO',
        output_path='/home/claude/laudo_clean.pdf',
    )
    print('OK ->', out)
