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
        cargo='Diretor',
        output_path='/home/claude/laudo_saida.pdf',
    )
"""

import re
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, HRFlowable, Table, TableStyle,
    PageBreak, NextPageTemplate, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_JUSTIFY
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
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
    """Divide um texto por ' | ' em lista de itens, removendo espaços extras."""
    return [item.strip() for item in texto.split('|') if item.strip()]


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
sSecT  = ParagraphStyle('SecT',     fontName='Helvetica-Bold',    fontSize=14,   leading=19, textColor=MAG,  spaceAfter=2)
sSubT  = ParagraphStyle('SubT',     fontName='Helvetica-Bold',    fontSize=11,   leading=15, textColor=TEAL, spaceAfter=3,  spaceBefore=8)
sBul   = ParagraphStyle('Bul',      fontName='Helvetica',         fontSize=10.5, leading=17, textColor=DARK, spaceAfter=4,  leftIndent=14, alignment=TA_JUSTIFY)
sHdr   = ParagraphStyle('Hdr',      fontName='Helvetica',         fontSize=8.5,  leading=12, textColor=GMID)
sLvlG  = ParagraphStyle('LvlG',     fontName='Helvetica-Bold',    fontSize=11,   leading=15, textColor=MAG,  spaceAfter=2,  spaceBefore=6)
sLvlS  = ParagraphStyle('LvlS',     fontName='Helvetica-Bold',    fontSize=10.5, leading=15, textColor=TEAL, spaceAfter=1,  spaceBefore=4)
sLvlB  = ParagraphStyle('LvlB',     fontName='Helvetica',         fontSize=10.5, leading=17, textColor=DARK, spaceAfter=4,  leftIndent=10, alignment=TA_JUSTIFY)
sFable = ParagraphStyle('Fable',    fontName='Helvetica-Oblique', fontSize=10.5, leading=18, textColor=DARK, spaceAfter=8,  leftIndent=14, rightIndent=14, alignment=TA_JUSTIFY)
sTB    = ParagraphStyle('TB',       fontName='Helvetica-Bold',    fontSize=10.5, leading=16, textColor=TEAL, spaceAfter=1)


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
    def __init__(self, paras, author):
        super().__init__(); self.paras=paras; self.author=author
        self._st = ParagraphStyle('FBx', fontName='Helvetica-Oblique', fontSize=10.5, leading=18, textColor=DARK, spaceAfter=8, leftIndent=4, rightIndent=4, alignment=TA_JUSTIFY)
        self._ast = ParagraphStyle('FAu', fontName='Helvetica-Oblique', fontSize=9.5, textColor=GMID, alignment=TA_RIGHT)
    def wrap(self, aw, ah):
        self._w=aw; h=24
        for par in self.paras:
            _,ph=Paragraph(par,self._st).wrap(aw-32,9999); h+=ph+8
        _,ah2=Paragraph(self.author,self._ast).wrap(aw-32,9999); h+=ah2+16
        self._h=h; return (aw,self._h)
    def draw(self):
        c=self.canv
        c.setFillColor(HexColor('#F3EEFB')); c.roundRect(0,0,self._w,self._h,6,fill=1,stroke=0)
        c.setStrokeColor(MAG); c.setLineWidth(0.5); c.roundRect(0,0,self._w,self._h,6,fill=0,stroke=1)
        y=self._h-16
        for par in self.paras:
            pp=Paragraph(par,self._st); _,ph=pp.wrap(self._w-32,9999); y-=ph; pp.drawOn(c,16,y); y-=8
        ap=Paragraph(self.author,self._ast); _,ah2=ap.wrap(self._w-32,9999); y-=ah2+8; ap.drawOn(c,16,y)


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════
def p(t):      return Paragraph(t, sBody)
def bl(t):     return Paragraph(f'• {t}', sBul)
def sp(h=0.3): return Spacer(1, h*cm)


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

        # Manchas orgânicas translúcidas (gradientes radiais simulados com círculos concêntricos)
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
        HRFlowable(width='55%', color=LAVANDA, thickness=1.5, spaceAfter=0),
        sp(0.6),
        Paragraph(f'<b>Cargo:</b> {cargo}',
            ParagraphStyle('CC', fontName='Helvetica', fontSize=12, textColor=CINZA_SF, alignment=1, spaceAfter=4)),
        Paragraph(mes_ano,
            ParagraphStyle('CD', fontName='Helvetica', fontSize=12, textColor=CINZA_SF, alignment=1)),
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
        Paragraph('Introdução', sSecT), SecLine(), sp(0.15), hdr(), sp(0.2),
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
        p('Um dos objetivos do 9&Self é oferecer demonstrações e argumentos que facilitem o caminho para '
          'maior respeito e tolerância consigo mesmo e com os outros, auxiliando na apreciação de dons, '
          'talentos e competências. Compreender a própria tipologia de personalidade provoca uma '
          'transformação favorável na vida das pessoas em uma grande variedade de situações pessoais e profissionais.'),
        p('O comportamento das pessoas é bastante variado, mas segue alguns padrões — modelos nos quais '
          'os indivíduos preferem observar o mundo e fazer julgamentos. As tipologias de personalidade '
          'são profundas e estruturantes no caráter de cada indivíduo. Não podemos alterar a base da '
          'nossa personalidade, mas podemos desenvolvê-la e ganhar maturidade.'),
        p('O <b>9&Self</b> está organizado da seguinte forma:'),
    ]
    for item in ['<b>Tipologia da Personalidade</b>','<b>Subtipo da Personalidade</b>',
                 '<b>Influência das Personalidades</b>','<b>Interação Social</b>',
                 'Estilo de Trabalho','Ambiente de Trabalho','Estresse da Personalidade',
                 'Comunicação e Feedback','Tendências na Liderança','Motivação',
                 'Desenvolvimento e Evolução da Personalidade','Fábula']:
        story.append(bl(item))

    # ══════════════════════════════════════════════════ TIPOLOGIA
    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph('Tipologia da Personalidade', sSecT), SecLine(), sp(0.15), hdr(), sp(0.2),
        p(sec.get('TIPOLOGIA', '')),
    ]))
    story += subsection('Padrão na Infância',
        p(sec.get('PADRAO_INFANCIA', '')),
    )

    # ══════════════════════════════════════════════════ PONTOS FORTES/FRACOS
    pf_partes = sec.get('PONTOS_FORTES', '').rsplit('\n', 1)
    pfx_partes = sec.get('PONTOS_FRACOS', '').rsplit('\n', 1)
    pf_texto, pf_itens = (pf_partes[0], split_pipes(pf_partes[1])) if len(pf_partes) == 2 else (sec.get('PONTOS_FORTES',''), [])
    pfx_texto, pfx_itens = (pfx_partes[0], split_pipes(pfx_partes[1])) if len(pfx_partes) == 2 else (sec.get('PONTOS_FRACOS',''), [])

    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph('Pontos Fortes e Fracos da Personalidade', sSecT),
        SecLine(), sp(0.15), hdr(), sp(0.4),
        p(f'{pf_texto} {pfx_texto}'.strip()),
        sp(0.2),
        DualGrid('✓  Pontos Fortes','⚠  Pontos Fracos', pf_itens, pfx_itens),
    ]))

    # ══════════════════════════════════════════════════ SUBTIPO
    story.append(PageBreak())
    asa_niveis = split_pipes(texto_asa) if '\n' not in texto_asa else texto_asa.split('\n')
    asa_niveis = [s.strip() for s in re.split(r'(?:\r?\n)+', texto_asa) if s.strip()]

    story.append(KeepTogether([
        Paragraph('Subtipo da Personalidade', sSecT),
        SecLine(), sp(0.15), hdr(), sp(0.2),
        Paragraph(f'Influência das Personalidades | {nome_asa} |', sSubT), sp(0.05),
        p(asa_niveis[0] if asa_niveis else ''),
    ]))
    for linha in asa_niveis[1:]:
        story.append(p(linha))

    story += subsection(
        f'Interação Social | {NOMES_SUBTIPO[subtipo_dom]} · {LABELS_SUBTIPO_LONGO[subtipo_int]} · '
        f'{LABELS_SUBTIPO_LONGO[subtipo_rem]} Reprimido |',
        p(texto_subtipo),
    )

    # ══════════════════════════════════════════════════ ESTILO DE TRABALHO
    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph('Estilo de Trabalho', sSecT), SecLine(), sp(0.15), hdr(), sp(0.2),
        Paragraph('Ambiente de Trabalho:', sSubT), sp(0.05),
        p(sec.get('AMBIENTE_TRABALHO', '')),
    ]))

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
        story += subsection('Estresse da Personalidade:',
            p(antes),
            sp(0.1),
            QuoteBox(citacao),
            sp(0.15),
            p(depois),
        )
    else:
        story += subsection('Estresse da Personalidade:', p(estresse_txt))

    # COMUNICAÇÃO + DualGrid Estilo ao Falar / Linguagem Corporal
    fala_itens = split_pipes(sec.get('FALA', ''))
    corporal_itens = split_pipes(sec.get('LINGUAGEM_CORPORAL', ''))
    comunicacao_content = [p(sec.get('COMUNICACAO', ''))]
    if fala_itens and corporal_itens:
        comunicacao_content += [
            sp(0.2),
            DualGrid('🗣 Estilo ao Falar','🤝 Linguagem Corporal', fala_itens, corporal_itens, hcolor=TEAL),
        ]
    elif corporal_itens:
        comunicacao_content += [
            sp(0.2),
            Paragraph('Linguagem Corporal:', sTB),
        ] + [bl(item) for item in corporal_itens]
    story += subsection('Comunicação:', *comunicacao_content)

    # FEEDBACK: pontos cegos / filtros + diretrizes
    cegos_itens = split_pipes(sec.get('PONTOS_CEGOS', ''))
    filtros_itens = split_pipes(sec.get('FILTROS_DISTORCOES', ''))
    feedback_itens = split_pipes(sec.get('FEEDBACK_ITENS', ''))

    feedback_content = [
        p('Evite que as tendências automáticas do seu estilo no Eneagrama interfiram na sua forma de '
          'liderar e desenvolver pessoas.'),
        sp(0.15),
        DualGrid('🎯 Pontos Cegos','🔍 Filtros e Distorções', cegos_itens, filtros_itens, hcolor=TEAL),
    ]
    if feedback_itens:
        feedback_content += [sp(0.2), FBBox('Diretrizes para o Feedback:', feedback_itens)]
    story += subsection('Feedback:', *feedback_content)

    # ══════════════════════════════════════════════════ LIDERANÇA E MOTIVAÇÃO
    aspectos_itens = split_pipes(sec.get('ASPECTOS_DESENVOLVER', ''))
    story.append(PageBreak())

    lid_block = [
        Paragraph('Liderança e Motivação', sSecT), SecLine(), sp(0.15), hdr(), sp(0.2),
        Paragraph('Tendências na Liderança:', sSubT), sp(0.05),
        p(sec.get('LIDERANCA', '')),
    ]
    if sec.get('TENDENCIAS_LIDERANCA'):
        lid_block.append(p(sec.get('TENDENCIAS_LIDERANCA', '')))
    if aspectos_itens:
        lid_block += [Paragraph('Principais Aspectos a Desenvolver:', sSubT), sp(0.05)]
        for item in aspectos_itens:
            titulo, texto = split_titulo_texto(item)
            if titulo:
                lid_block.append(KeepTogether([Paragraph(f'<b>{titulo}</b>', sTB), p(texto)]))
            else:
                lid_block.append(p(texto))
    story.append(KeepTogether(lid_block))

    # MOTIVAÇÃO
    motivacao_itens = split_pipes(sec.get('MOTIVACAO', ''))
    story += subsection('Motivação:', *[bl(item) for item in motivacao_itens])

    # AUTODOMÍNIO
    autodominio_itens = split_pipes(sec.get('AUTODOMINIO', ''))
    niveis_autodom = []
    for item in autodominio_itens:
        titulo, texto = split_titulo_texto(item)
        titulo_fmt = f'Nível {titulo}' if titulo else ''
        niveis_autodom.append(nivel(titulo_fmt, texto))
    story += subsection('Autodomínio:', *niveis_autodom)

    # ══════════════════════════════════════════════════ HÁBITOS POSITIVOS
    habitos_itens = split_double_pipes(sec.get('HABITOS', ''))
    story.append(PageBreak())

    habitos_block = [
        Paragraph('Crie Hábitos Positivos para sua Personalidade', sSecT),
        SecLine(), sp(0.15), hdr(), sp(0.2),
        p(f'O tipo {nome_tipo} deve desenvolver deliberadamente os seguintes hábitos saudáveis:'),
    ]
    primeiro_habito = True
    for item in habitos_itens:
        titulo, texto = split_titulo_texto(item)
        bloco = KeepTogether([Paragraph(f'<b>{titulo}</b>', sTB), p(texto)]) if titulo else p(texto)
        if primeiro_habito:
            habitos_block.append(bloco)
            primeiro_habito = False
        else:
            story_extra = bloco
    story.append(KeepTogether(habitos_block))
    if len(habitos_itens) > 1:
        for item in habitos_itens[1:]:
            titulo, texto = split_titulo_texto(item)
            if titulo:
                story.append(KeepTogether([Paragraph(f'<b>{titulo}</b>', sTB), p(texto)]))
            else:
                story.append(p(texto))

    # FRASES COMUNS
    frases_itens = split_pipes(sec.get('FRASES_COMUNS', ''))
    story += subsection('Frases Comuns:', *[bl(item) for item in frases_itens])

    # ══════════════════════════════════════════════════ NÍVEIS DE SAÚDE
    niveis_itens = split_pipes(sec.get('NIVEIS_SAUDE', ''))
    # niveis_itens vem como [titulo1, texto1, titulo2, texto2, ...]
    niveis_pares = []
    for i in range(0, len(niveis_itens) - 1, 2):
        titulo_raw = re.sub(r'^N\d+:\s*', '', niveis_itens[i]).strip()
        niveis_pares.append((titulo_raw, niveis_itens[i+1]))

    story.append(PageBreak())
    health_block = [
        Paragraph('Níveis de Saúde da Personalidade', sSecT),
        SecLine(), sp(0.15), hdr(), sp(0.2),
        p(f'A personalidade é dinâmica e se move ao longo de <b>9 níveis de desenvolvimento e maturidade '
          f'individual</b>. Vale ressaltar que pressões e fatores externos podem alterar temporariamente '
          f'esses níveis no tipo {nome_tipo}.'),
        sp(0.2),
        Paragraph('a) Nível Saudável (Elevado)', sLvlG),
    ]
    if len(niveis_pares) > 0:
        titulo, texto = niveis_pares[0]
        health_block.append(nivel(f'Nível 1 - {titulo}', texto))
    story.append(KeepTogether(health_block))

    grupos = {3: 'b) Nível Médio', 6: 'c) Nível Não Saudável'}
    for idx in range(1, min(len(niveis_pares), 9)):
        if idx in grupos:
            story.append(Paragraph(grupos[idx], sLvlG))
        titulo, texto = niveis_pares[idx]
        story.append(nivel(f'Nível {idx+1} - {titulo}', texto))

    # ══════════════════════════════════════════════════ DESENVOLVIMENTO
    story.append(PageBreak())
    story.append(KeepTogether([
        Paragraph('Desenvolvimento e Evolução da Personalidade', sSecT),
        SecLine(), sp(0.15), hdr(), sp(0.2),
        p(sec.get('DESENVOLVIMENTO', '')),
    ]))
    if sec.get('INFOBOX_DESENVOLVIMENTO'):
        story.append(InfoBox(sec.get('INFOBOX_DESENVOLVIMENTO', '')))

    # ══════════════════════════════════════════════════ FÁBULA
    fabula_txt = sec.get('FABULA', '')
    fabula_titulo = 'Marcenaria'
    fabula_corpo = fabula_txt
    if ':' in fabula_txt[:30]:
        fabula_titulo, _, fabula_corpo = fabula_txt.partition(':')
        fabula_titulo = fabula_titulo.strip()
        fabula_corpo = fabula_corpo.strip()

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
    story.append(KeepTogether([
        Paragraph('Fábula', sSecT), SecLine(), sp(0.15), hdr(), sp(0.2),
        Paragraph(fabula_titulo,
            ParagraphStyle('FT',fontName='Helvetica-Bold',fontSize=17,textColor=MAG,alignment=1,spaceAfter=12,spaceBefore=4)),
    ]))
    story.append(FableBox(paras_finais, 'Autor Desconhecido'))

    # PLAYLIST
    playlist_txt = sec.get('PLAYLIST', '')
    story.append(KeepTogether([
        sp(0.8),
        Paragraph('Playlist da Personalidade', sSubT), sp(0.05),
        p('Se desejar assistir a vídeos detalhados sobre o seu perfil, basta acessar o endereço '
          'eletrônico abaixo para acompanhar uma seleção de conteúdos preparados sobre a sua '
          'personalidade. Recomenda-se iniciar a partir do vídeo 3 desta lista de reprodução.'),
        sp(0.15),
        Table([[Paragraph(
            re.sub(r'^(Link da Playlist[^:]*:)', r'<b>\1</b>\n', playlist_txt),
            ParagraphStyle('LK',fontName='Helvetica',fontSize=10,textColor=TEAL,leading=16,alignment=1))
        ]], colWidths=[TW], style=TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),TBOX),('LINEBEFORE',(0,0),(0,-1),3,TEAL),
            ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),
            ('LEFTPADDING',(0,0),(-1,-1),16),('RIGHTPADDING',(0,0),(-1,-1),16),
        ])),
    ]))

    doc.build(story)
    return output_path


if __name__ == '__main__':
    out = gerar_laudo(
        tipo=1, asa_dominante=2,
        subtipo_dom='AP', subtipo_int='1A1', subtipo_rem='SOC',
        nome='Fabiano de Sousa Vaz de Campos',
        cargo='Diretor',
        output_path='/home/claude/laudo_clean.pdf',
    )
    print('OK ->', out)
