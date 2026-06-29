# INTEGRAÇÃO MERCADO PAGO → 9&Self
## Guia de configuração passo a passo

---

## 1. ARQUIVOS A SUBIR NO GITHUB

Adicione `webhook_mercadopago.py` dentro da pasta `functions/` do repositório:
```
app-eneagrama/
└── functions/
    ├── main.py                    ← já existe, NÃO MEXA
    ├── requirements.txt           ← substitua pelo novo
    ├── webhook_mercadopago.py     ← NOVO — adicione este
    └── ...
```

---

## 2. CONFIGURAR GMAIL (App Password)

1. Acesse: https://myaccount.google.com/security
2. Ative a verificação em 2 etapas (se não estiver ativa)
3. Vá em "Senhas de app" → gere uma senha para "Correio"
4. Copie a senha gerada (ex: `abcd efgh ijkl mnop`)

No terminal, configure a variável:
```bash
firebase functions:config:set gmail.pass="abcdefghijklmnop"
```
(sem espaços na senha)

---

## 3. CONFIGURAR TOKEN DO MERCADO PAGO

1. Acesse: https://www.mercadopago.com.br/developers/panel
2. Vá em "Credenciais" → copie o **Access Token de PRODUÇÃO**
   (começa com `APP_USR-...`)

```bash
firebase functions:config:set mercadopago.token="APP_USR-XXXXX..."
```

---

## 4. DEPLOY DA FUNÇÃO

```bash
# Dentro da pasta app-eneagrama/
firebase deploy --only functions:webhookMercadoPago
```

A URL gerada será algo como:
```
https://us-central1-entrevista-inicial.cloudfunctions.net/webhookMercadoPago
```

---

## 5. CONFIGURAR WEBHOOK NO MERCADO PAGO

1. Acesse: https://www.mercadopago.com.br/developers/panel/notifications
2. Clique em "Webhooks" → "Adicionar"
3. Cole a URL da função acima
4. Selecione evento: **Pagamentos**
5. Salve

---

## 6. ESTRUTURA NO FIREBASE (automática)

Quando um pagamento for aprovado, o código é salvo em `nself_codigos`:
```json
{
  "codigo": "ABC123",
  "nomeDestinatario": "Maria Silva",
  "email": "maria@email.com",
  "empresa": null,
  "tipo": "PF",
  "status": "Pendente",
  "origem": "mercadopago",
  "pagamentoId": "123456789",
  "valorPago": 89.10,
  "linkTeste": "https://luciakratz.github.io/app-eneagrama/index.html?code=ABC123",
  "criadoEm": "..."
}
```

O código aparece automaticamente na tabela de Códigos do painel Admin.

---

## 7. TESTAR

No painel do Mercado Pago Developers, use o botão "Simular pagamento" 
para disparar um webhook de teste antes de ir para produção.
