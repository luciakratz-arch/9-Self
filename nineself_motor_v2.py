"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        9&Self — MOTOR DE GERAÇÃO DE LAUDO + PLANO DE AÇÃO (v2)             ║
║        Dra. Lucia Kratz · CRP 09/20590                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

USO:
    python nineself_motor_v2.py
    python nineself_motor_v2.py --criar-templates
    python nineself_motor_v2.py --tipo 7 --asa 8 --subtipo ap_1a1_soc

ESTRUTURA DE ARQUIVOS:
    banco_dados/
        tipo_1.txt ... tipo_9.txt
    output/
        laudo_tipo7_asa8_ap_1a1_soc.md   ← Markdown para converter em PDF
        laudo_tipo7_asa8_ap_1a1_soc.json ← JSON para Firebase/App
"""

import os
import re
import json
import argparse
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES DO SISTEMA
# ══════════════════════════════════════════════════════════════════════════════

NOMES_TIPO = {
    1: "Perfeição e Excelência",
    2: "Prestativo e Relacional",
    3: "Performance e Imagem",
    4: "Autêntico e Profundo",
    5: "Observador e Privacidade",
    6: "Precavido e Questionador",
    7: "Visionário e Otimista",
    8: "Desafiador e Controlador",
    9: "Harmônico e Diplomático",
}

TRACOS_TIPO = {
    1: "Traço Tipo 1 — Perfeição e Excelência",
    2: "Traço Tipo 2 — Prestativo e Relacional",
    3: "Traço Tipo 3 — Performance e Imagem",
    4: "Traço Tipo 4 — Autêntico e Profundo",
    5: "Traço Tipo 5 — Observador e Privacidade",
    6: "Traço Tipo 6 — Precavido e Questionador",
    7: "Traço Tipo 7 — Visionário e Otimista",
    8: "Traço Tipo 8 — Desafiador e Controlador",
    9: "Traço Tipo 9 — Harmônico e Diplomático",
}

NOMES_SUBTIPO = {
    "ap":  "Autopreservação",
    "1a1": "1 a 1",
    "soc": "Social",
}

ASAS_VALIDAS = {
    1: [9, 2], 2: [1, 3], 3: [2, 4], 4: [3, 5],
    5: [4, 6], 6: [5, 7], 7: [6, 8], 8: [7, 9], 9: [8, 1],
}

# Todas as combinações possíveis de subtipo
COMBINACOES_SUBTIPO = [
    "AP_1A1_SOC", "AP_SOC_1A1",
    "1A1_AP_SOC", "1A1_SOC_AP",
    "SOC_AP_1A1", "SOC_1A1_AP",
]


# ══════════════════════════════════════════════════════════════════════════════
# 1. PARSER DO BANCO DE DADOS
# ══════════════════════════════════════════════════════════════════════════════

def carregar_banco_dados(caminho_pasta: str) -> dict:
    """
    Lê os arquivos tipo_N.txt e extrai blocos usando tags === SECAO ===.

    Retorna:
        {
            1: {"PONTOS_FORTES": [...], "ASA_9": "...", ...},
            2: {...},
            ...
        }
    """
    banco = {}

    for num in range(1, 10):
        arquivo = os.path.join(caminho_pasta, f"tipo_{num}.txt")
        if not os.path.exists(arquivo):
            print(f"[AVISO] Arquivo não encontrado: {arquivo}")
            banco[num] = {}
            continue

        with open(arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()

        banco[num] = _parsear_blocos(conteudo, num)
        n = len(banco[num])
        print(f"[OK] Tipo {num} ({NOMES_TIPO[num]}) — {n} seções carregadas")

    return banco


def _parsear_blocos(conteudo: str, tipo_num: int) -> dict:
    """
    Extrai todos os blocos === NOME === do conteúdo do arquivo.
    Blocos com | viram listas. AUTODOMINIO e NIVEIS_SAUDE têm parsing especial.
    """
    resultado = {}

    # Divide o conteúdo pelas tags === NOME ===
    padrao = re.compile(r"===\s*([A-Z0-9_]+)\s*===", re.IGNORECASE)
    partes = padrao.split(conteudo)

    # partes[0] = cabeçalho (ignorar)
    # partes[1,3,5...] = nomes das seções
    # partes[2,4,6...] = conteúdos
    i = 1
    while i < len(partes) - 1:
        chave = partes[i].strip().upper()
        valor = partes[i + 1].strip() if (i + 1) < len(partes) else ""

        # Ignora blocos vazios ou placeholders (qualquer texto entre colchetes)
        import re as _re
        valor_strip = valor.strip()
        if not valor_strip or _re.match(r'^\[.*\]$', valor_strip, _re.DOTALL):
            resultado[chave] = ""
            i += 2
            continue

        # ── Blocos que viram lista (separados por |) ──────────────────────
        BLOCOS_LISTA = {
            "PONTOS_FORTES", "PONTOS_FRACOS", "FRASES_COMUNS",
            "PLAYLIST", "FEEDBACK_ITENS", "FALA",
            "LINGUAGEM_CORPORAL", "PONTOS_CEGOS", "FILTROS_DISTORCOES",
        }
        if chave in BLOCOS_LISTA:
            # Pega só a linha com | (ignora parágrafos descritivos antes)
            linhas = valor.split("\n")
            linha_lista = next(
                (l for l in linhas if "|" in l and len(l.strip()) > 3), None
            )
            if linha_lista:
                resultado[chave] = [
                    item.strip() for item in linha_lista.split("|")
                    if item.strip()
                ]
            else:
                resultado[chave] = [v.strip() for v in valor.split("|") if v.strip()]

        # ── AUTODOMINIO: Máximo | Moderado | Baixo ───────────────────────
        elif chave == "AUTODOMINIO":
            partes_auto = [p.strip() for p in valor.split("|")]
            resultado[chave] = {
                "maximo":   partes_auto[0] if len(partes_auto) > 0 else "",
                "moderado": partes_auto[1] if len(partes_auto) > 1 else "",
                "baixo":    partes_auto[2] if len(partes_auto) > 2 else "",
            }

        # ── NIVEIS_SAUDE: N1: texto | N2: texto | ... ────────────────────
        elif chave == "NIVEIS_SAUDE":
            niveis = {}
            for item in valor.split("|"):
                item = item.strip()
                if ":" in item:
                    nivel, texto = item.split(":", 1)
                    niveis[nivel.strip()] = texto.strip()
            resultado[chave] = niveis

        # ── Texto simples ─────────────────────────────────────────────────
        else:
            resultado[chave] = valor

        i += 2

    return resultado


# ══════════════════════════════════════════════════════════════════════════════
# 2. GERADOR DO TEXTO DO LAUDO
# ══════════════════════════════════════════════════════════════════════════════

def gerar_texto_laudo(
    banco: dict,
    tipo: int,
    asa: int,
    ordem_subtipo: list,   # ex: ["ap", "1a1", "soc"]
    nome_cliente: str = "Cliente",
) -> dict:
    """
    Monta o laudo completo como dicionário de seções.
    Cada seção = uma parte do PDF (com regras de quebra de página).

    Retorna dict com:
        - 'texto_markdown': string Markdown pronta para conversão PDF
        - 'secoes': dict com cada bloco separado
        - 'plano_acao': Markdown do PDI
        - 'meta': metadados do resultado
        - 'erros': lista de avisos
    """
    erros = []
    dados = banco.get(tipo, {})

    if not dados:
        raise ValueError(f"Tipo {tipo} não encontrado no banco de dados.")
    if asa not in ASAS_VALIDAS.get(tipo, []):
        erros.append(f"[AVISO] Asa {asa} inválida para Tipo {tipo}.")

    # ── Helper: busca bloco com aviso se não encontrado ───────────────────
    def B(chave: str, fallback: str = "") -> str:
        v = dados.get(chave.upper(), fallback)
        if not v:
            erros.append(f"Bloco '{chave}' vazio para Tipo {tipo}.")
        return v if isinstance(v, str) else fallback

    def BL(chave: str) -> list:
        v = dados.get(chave.upper(), [])
        if not v:
            erros.append(f"Bloco lista '{chave}' vazio para Tipo {tipo}.")
        return v if isinstance(v, list) else []

    # ── Chave da combinação de subtipo ────────────────────────────────────
    combo_key = "_".join([s.upper() for s in ordem_subtipo])
    chave_sub = f"SUBTIPO_{combo_key}"
    texto_subtipo = dados.get(chave_sub, "")
    if not texto_subtipo:
        # Fallback: subtipo dominante
        chave_dom = f"SUBTIPO_{ordem_subtipo[0].upper()}"
        texto_subtipo = dados.get(chave_dom, "")
        if texto_subtipo:
            erros.append(f"Combinação '{combo_key}' não encontrada. Usando dominante.")
        else:
            erros.append(f"Nenhum texto de subtipo encontrado.")

    # ── Chave da asa ──────────────────────────────────────────────────────
    chave_asa = f"ASA_{asa}"
    texto_asa = dados.get(chave_asa, "")
    if not texto_asa:
        erros.append(f"Bloco '{chave_asa}' vazio para Tipo {tipo}.")

    # ── Metadados ─────────────────────────────────────────────────────────
    meta = {
        "tipo":          tipo,
        "nome_tipo":     NOMES_TIPO[tipo],
        "traco_tipo":    TRACOS_TIPO[tipo],
        "asa":           asa,
        "subtipo_dom":   ordem_subtipo[0],
        "subtipo_int":   ordem_subtipo[1],
        "subtipo_rem":   ordem_subtipo[2],
        "nome_sub_dom":  NOMES_SUBTIPO.get(ordem_subtipo[0], ordem_subtipo[0]),
        "nome_sub_int":  NOMES_SUBTIPO.get(ordem_subtipo[1], ordem_subtipo[1]),
        "nome_sub_rem":  NOMES_SUBTIPO.get(ordem_subtipo[2], ordem_subtipo[2]),
        "combinacao":    combo_key,
        "nome_cliente":  nome_cliente,
        "erros":         erros,
    }

    # ══════════════════════════════════════════════════════════════════════
    # MONTAGEM DO TEXTO CORRIDO (Markdown → PDF)
    # Regra de layout:
    #   - ## = NOVA PÁGINA (PageBreak antes)
    #   - ### = subtítulo, flui na MESMA PÁGINA (sem PageBreak)
    # ══════════════════════════════════════════════════════════════════════

    linhas = []

    # ── CAPA ──────────────────────────────────────────────────────────────
    linhas += [
        f"# {meta['traco_tipo']}",
        f"### Relatório de Personalidade — {nome_cliente}",
        f"*Asa {asa} · Subtipo: {meta['nome_sub_dom']} (dom) · "
        f"{meta['nome_sub_int']} (int) · {meta['nome_sub_rem']} (rem)*",
        "",
        "---",
        "",
    ]

    # ── SEÇÃO 1: TIPOLOGIA BASE ── [NOVA PÁGINA]
    # Subtópicos (Padrão Infância, Interação Social) fluem na mesma página
    linhas += [
        "## Tipologia da Personalidade",              # ← PageBreak aqui
        "",
        B("TIPOLOGIA"),
        "",
        "### Padrão na Infância",                     # ← SEM PageBreak (flui)
        "",
        B("PADRAO_INFANCIA"),
        "",
        "### Interação Social",                       # ← SEM PageBreak (flui)
        "",
        B("INTERACAO_SOCIAL"),
        "",
    ]

    # ── SEÇÃO 2: PONTOS FORTES E FRACOS ── [NOVA PÁGINA]
    pf = BL("PONTOS_FORTES")
    pw = BL("PONTOS_FRACOS")
    linhas += [
        "## Pontos Fortes e Fracos",                  # ← PageBreak aqui
        "",
        "### Pontos Fortes",                          # ← SEM PageBreak
        "",
    ]
    for item in pf:
        linhas.append(f"- ✅ {item}")
    linhas += ["", "### Pontos Fracos", ""]           # ← SEM PageBreak
    for item in pw:
        linhas.append(f"- ⚠️ {item}")
    linhas.append("")

    # ── SEÇÃO 3: SUBTIPO ── [NOVA PÁGINA]
    linhas += [
        "## Subtipo da Personalidade",                # ← PageBreak aqui
        "",
        f"**Dominante:** {meta['nome_sub_dom']} · "
        f"**Intermediário:** {meta['nome_sub_int']} · "
        f"**Remissivo:** {meta['nome_sub_rem']}",
        "",
        texto_subtipo,
        "",
    ]

    # ── SEÇÃO 4: ESTILO DE TRABALHO ── [NOVA PÁGINA]
    # Comunicação e Estresse fluem na mesma página
    linhas += [
        "## Estilo de Trabalho",                      # ← PageBreak aqui
        "",
        B("AMBIENTE_TRABALHO"),
        "",
        "### Estresse da Personalidade",              # ← SEM PageBreak (flui)
        "",
        B("ESTRESSE"),
        "",
        "### Comunicação",                            # ← SEM PageBreak (flui)
        "",
        B("COMUNICACAO"),
        "",
    ]

    # ── SEÇÃO 5: ASA ── [NOVA PÁGINA]
    linhas += [
        f"## Asa da Personalidade — Asa {asa}",       # ← PageBreak aqui
        "",
        texto_asa,
        "",
    ]

    # ── SEÇÃO 6: LIDERANÇA E MOTIVAÇÃO ── [NOVA PÁGINA]
    # Feedback e Aspectos fluem na mesma página
    linhas += [
        "## Liderança e Motivação",                   # ← PageBreak aqui
        "",
        B("LIDERANCA"),
        "",
        "### Tendências na Liderança",                # ← SEM PageBreak (flui)
        "",
        B("TENDENCIAS_LIDERANCA"),
        "",
        "### Feedback",                               # ← SEM PageBreak (flui)
        "",
    ]
    fb = BL("FEEDBACK_ITENS")
    for item in fb:
        linhas.append(f"- {item}")
    linhas += [
        "",
        "### Principais Aspectos a Desenvolver",      # ← SEM PageBreak (flui)
        "",
        B("ASPECTOS_DESENVOLVER"),
        "",
        "### Motivação",                              # ← SEM PageBreak (flui)
        "",
        B("MOTIVACAO"),
        "",
    ]

    # ── SEÇÃO 7: PLANO DE AÇÃO (PDI) ── [NOVA PÁGINA]
    # Gerado pela função separada
    plano_md = gerar_plano_acao_markdown(dados, tipo, asa, ordem_subtipo[2], meta)
    linhas += [plano_md, ""]

    # ── SEÇÃO 8: HÁBITOS ── [NOVA PÁGINA]
    linhas += [
        "## Crie Hábitos Positivos",                  # ← PageBreak aqui
        "",
        B("HABITOS"),
        "",
    ]

    # ── SEÇÃO 9: NÍVEIS DE SAÚDE ── [NOVA PÁGINA]
    autodominio = dados.get("AUTODOMINIO", {})
    niveis = dados.get("NIVEIS_SAUDE", {})
    linhas += [
        "## Níveis de Saúde da Personalidade",        # ← PageBreak aqui
        "",
        "### Autodomínio",                            # ← SEM PageBreak (flui)
        "",
        f"**Máximo:** {autodominio.get('maximo', '')}",
        "",
        f"**Moderado:** {autodominio.get('moderado', '')}",
        "",
        f"**Baixo:** {autodominio.get('baixo', '')}",
        "",
        "### Frases Comuns",                          # ← SEM PageBreak (flui)
        "",
    ]
    frases = BL("FRASES_COMUNS")
    for fr in frases:
        linhas.append(f'> "{fr}"')
    linhas.append("")

    # ── SEÇÃO 10: DESENVOLVIMENTO ── [NOVA PÁGINA]
    linhas += [
        "## Desenvolvimento e Evolução",              # ← PageBreak aqui
        "",
        B("DESENVOLVIMENTO"),
        "",
        B("INFOBOX_DESENVOLVIMENTO"),
        "",
    ]

    # ── SEÇÃO 11: FÁBULA ── [NOVA PÁGINA]
    linhas += [
        "## Fábula",                                  # ← PageBreak aqui
        "",
        B("FABULA"),
        "",
    ]
    playlist = BL("PLAYLIST")
    if playlist:
        linhas += ["### Playlist", ""]
        for m in playlist:
            linhas.append(f"- 🎵 {m}")
        linhas.append("")

    texto_final = "\n".join(linhas)

    return {
        "meta":            meta,
        "texto_markdown":  texto_final,
        "plano_acao_md":   plano_md,
        "erros":           erros,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. MÓDULO DO PLANO DE AÇÃO (PDI) — VISUAL / MARKDOWN
# ══════════════════════════════════════════════════════════════════════════════

def gerar_plano_acao_markdown(
    dados: dict,
    tipo: int,
    asa: int,
    subtipo_remissivo: str,
    meta: dict,
) -> str:
    """
    Gera o bloco Markdown do PDI (Plano de Ação e Desenvolvimento Individual).
    Injeta dinamicamente os conteúdos das tags do tipo.
    Posição no PDF: imediatamente após Liderança, antes de Hábitos.
    """

    def B(chave: str) -> str:
        v = dados.get(chave.upper(), "")
        return v if isinstance(v, str) else ""

    def BL(chave: str) -> list:
        v = dados.get(chave.upper(), [])
        return v if isinstance(v, list) else []

    autodominio = dados.get("AUTODOMINIO", {
        "maximo": "—", "moderado": "—", "baixo": "—"
    })
    filtros     = BL("FILTROS_DISTORCOES")
    corp        = BL("LINGUAGEM_CORPORAL")
    habitos_txt = B("HABITOS")
    aspectos    = B("ASPECTOS_DESENVOLVER")
    frases      = BL("FRASES_COMUNS")
    nome_sub_rem = NOMES_SUBTIPO.get(subtipo_remissivo, subtipo_remissivo)

    # Montar tabela de hábitos cruzados
    max_linhas = max(len(filtros), len(corp), 1)
    tabela_habitos = (
        "| O que monitorar (Filtros Mentais) | Onde sentir no corpo | Ação Corretiva |\n"
        "| :--- | :--- | :--- |\n"
    )
    for i in range(max_linhas):
        col1 = filtros[i] if i < len(filtros) else "—"
        col2 = corp[i]    if i < len(corp)    else "—"
        col3 = habitos_txt if i == 0 else "—"
        tabela_habitos += f"| {col1} | {col2} | {col3} |\n"

    # Frases de reflexão
    frases_md = "\n".join([f'> "{f}"' for f in frases]) if frases else "> —"

    plano = f"""## Plano de Ação e Desenvolvimento Individual (PDI)

> **Instrução Prática:** Este plano foi gerado com base nas intersecções da sua tipologia, asa e ordem instintiva. Utilize as escalas abaixo para monitorar sua evolução e quebrar o automatismo da sua mente.

---

### 1. Escala de Autodomínio — Termômetro de Presença

*Identifique conscientemente em qual nível você operou nas últimas 48 horas.*

| Nível de Presença | Estado Comportamental | Indicador Visual |
| :--- | :--- | :--- |
| **MÁXIMO (Saudável)** | Comportamento integrado, flexível e focado no aqui-agora. | ● ● ● ○ ○ ○ ○ ○ ○ — *Presença e Alta Performance* |
| **MODERADO (Médio)** | Flutuação entre consciência e automatismo reativo. | ○ ○ ○ ● ● ● ○ ○ ○ — *Alerta: Transe Moderado* |
| **BAIXO (Inseguro)** | Totalmente preso em defesas mecânicas e estresse agudo. | ○ ○ ○ ○ ○ ○ ● ● ● — *Perigo: Zona Crítica* |

> **Seu mapa de Autodomínio ({TRACOS_TIPO[tipo]}):**
>
> **Máximo:** {autodominio.get('maximo', '—')}
>
> **Moderado:** {autodominio.get('moderado', '—')}
>
> **Baixo:** {autodominio.get('baixo', '—')}

---

### 2. Diretrizes de Evolução & Metas Acionáveis

> *Escolha apenas um tópico abaixo para focar nos próximos 21 dias. A mudança real exige foco direcionado.*

{aspectos if aspectos else '— A ser preenchido —'}

---

### 3. Roteiro de Hábitos Concretos — Checklist de Gatilhos

*Use esta matriz como rastreador diário para desarmar as armadilhas da sua mente.*

{tabela_habitos}

---

### 4. Monitoramento de Convívio e Inteligência Emocional

*Atribua uma nota de 1 a 5 para sua constância diária nos seguintes pilares:*

- [ ] **Mapeei meus pontos cegos nas reuniões de equipe:** `1 · 2 · 3 · 4 · 5`
- [ ] **Observei meus gatilhos corporais antes de responder:** `1 · 2 · 3 · 4 · 5`
- [ ] **Apliquei as diretrizes para dar/receber feedback:** `1 · 2 · 3 · 4 · 5`

---

### 5. Ativação do Subtipo Remissivo — {nome_sub_rem}

> *Seu subtipo remissivo é o instinto que exige mais esforço e energia. Pequenas ações nessa direção geram grandes transformações.*

{dados.get(f'SUBTIPO_{subtipo_remissivo.upper()}', '— A ser preenchido —')}

---

### Frases de Reflexão para o Despertar Diário

> *Monitore a frequência com que estas ideias ecoam na sua mente. Elas revelam a voz oculta da sua fixação.*

{frases_md}

---"""

    return plano


# ══════════════════════════════════════════════════════════════════════════════
# 4. EXPORTADORES
# ══════════════════════════════════════════════════════════════════════════════

def exportar_markdown(resultado: dict, caminho: str):
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(resultado["texto_markdown"])
    print(f"[OK] Markdown: {caminho}")


def exportar_json(resultado: dict, caminho: str):
    # Remove o texto_markdown do JSON (muito longo), mantém só as seções
    payload = {k: v for k, v in resultado.items() if k != "texto_markdown"}
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON: {caminho}")


# ══════════════════════════════════════════════════════════════════════════════
# 5. CRIADOR DE TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

def criar_template_tipo(tipo: int, pasta: str):
    """Cria arquivo tipo_N.txt com todas as seções vazias para preenchimento."""
    secoes = [
        ("TIPOLOGIA",              "Texto base do tipo"),
        ("PADRAO_INFANCIA",        "Padrão na infância"),
        ("INTERACAO_SOCIAL",       "Interação social"),
        ("PONTOS_FORTES",          "item 1 | item 2 | item 3"),
        ("PONTOS_FRACOS",          "item 1 | item 2 | item 3"),
        (f"ASA_{ASAS_VALIDAS[tipo][0]}", "Texto da asa"),
        (f"ASA_{ASAS_VALIDAS[tipo][1]}", "Texto da asa"),
        ("SUBTIPO_AP_1A1_SOC",     "Texto da combinação"),
        ("SUBTIPO_AP_SOC_1A1",     "Texto da combinação"),
        ("SUBTIPO_1A1_AP_SOC",     "Texto da combinação"),
        ("SUBTIPO_1A1_SOC_AP",     "Texto da combinação"),
        ("SUBTIPO_SOC_AP_1A1",     "Texto da combinação"),
        ("SUBTIPO_SOC_1A1_AP",     "Texto da combinação"),
        ("AMBIENTE_TRABALHO",      "Texto"),
        ("ESTRESSE",               "Texto"),
        ("COMUNICACAO",            "Texto"),
        ("FALA",                   "item 1 | item 2 | item 3"),
        ("LINGUAGEM_CORPORAL",     "item 1 | item 2 | item 3"),
        ("PONTOS_CEGOS",           "item 1 | item 2 | item 3"),
        ("FILTROS_DISTORCOES",     "item 1 | item 2 | item 3"),
        ("FEEDBACK_ITENS",         "item 1 | item 2 | item 3"),
        ("LIDERANCA",              "Texto"),
        ("TENDENCIAS_LIDERANCA",   "Texto"),
        ("ASPECTOS_DESENVOLVER",   "Texto"),
        ("MOTIVACAO",              "Texto"),
        ("AUTODOMINIO",            "Máximo: texto | Moderado: texto | Baixo: texto"),
        ("HABITOS",                "Texto"),
        ("FRASES_COMUNS",          "frase 1 | frase 2 | frase 3"),
        ("NIVEIS_SAUDE",           "N1: texto | N2: texto | N3: texto | N4: texto | N5: texto | N6: texto | N7: texto | N8: texto | N9: texto"),
        ("DESENVOLVIMENTO",        "Texto"),
        ("INFOBOX_DESENVOLVIMENTO","Texto"),
        ("FABULA",                 "Texto"),
        ("PLAYLIST",               "Música 1 | Música 2 | Música 3"),
    ]

    linhas = [
        f"# ARQUIVO DE CONTEÚDO — {TRACOS_TIPO[tipo]}",
        f"# Banco de Dados 9&Self · Dra. Lucia Kratz · CRP 09/20590",
        "",
    ]
    for chave, placeholder in secoes:
        linhas += [f"=== {chave} ===", placeholder, ""]

    caminho = os.path.join(pasta, f"tipo_{tipo}.txt")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print(f"[OK] Template: {caminho}")


# ══════════════════════════════════════════════════════════════════════════════
# EXECUÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

    PASTA_BANCO  = "./banco_dados"
    PASTA_OUTPUT = "./output"
    os.makedirs(PASTA_BANCO,  exist_ok=True)
    os.makedirs(PASTA_OUTPUT, exist_ok=True)

    parser = argparse.ArgumentParser(description="9&Self — Gerador de Laudo")
    parser.add_argument("--criar-templates", action="store_true")
    parser.add_argument("--tipo",    type=int, default=7)
    parser.add_argument("--asa",     type=int, default=8)
    parser.add_argument("--subtipo", type=str, default="ap_1a1_soc")
    parser.add_argument("--cliente", type=str, default="Cliente Teste")
    args = parser.parse_args()

    if args.criar_templates:
        print("=== Criando templates ===")
        for t in range(1, 10):
            criar_template_tipo(t, PASTA_BANCO)
        print("\nTemplates criados! Preencha os arquivos em ./banco_dados/")
        exit(0)

    print(f"\n=== 9&Self — Motor de Laudo v2 ===")
    banco = carregar_banco_dados(PASTA_BANCO)

    ordem = [s.strip().lower() for s in args.subtipo.split("_")]
    if len(ordem) != 3:
        print("[ERRO] --subtipo deve ter formato: ap_1a1_soc")
        exit(1)

    print(f"\nGerando laudo:")
    print(f"  Tipo:    {args.tipo} — {NOMES_TIPO.get(args.tipo,'')}")
    print(f"  Asa:     {args.asa}")
    print(f"  Subtipo: {' > '.join(ordem)}")
    print(f"  Cliente: {args.cliente}")

    resultado = gerar_texto_laudo(banco, args.tipo, args.asa, ordem, args.cliente)

    slug = f"tipo{args.tipo}_asa{args.asa}_{args.subtipo}"
    exportar_markdown(resultado, os.path.join(PASTA_OUTPUT, f"laudo_{slug}.md"))
    exportar_json(resultado,     os.path.join(PASTA_OUTPUT, f"laudo_{slug}.json"))

    print(f"\n=== RESULTADO ===")
    print(f"Tipo:     {resultado['meta']['traco_tipo']}")
    print(f"Asa:      Asa {resultado['meta']['asa']}")
    print(f"Subtipo:  {resultado['meta']['nome_sub_dom']} · {resultado['meta']['nome_sub_int']} · {resultado['meta']['nome_sub_rem']}")

    if resultado["erros"]:
        print(f"\nAvisos ({len(resultado['erros'])}):")
        for e in resultado["erros"]:
            print(f"  {e}")

    print("\n[CONCLUÍDO]")
