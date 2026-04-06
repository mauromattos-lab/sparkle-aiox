# Playbook Comercial Mauro — Pipeline Sparkle v1
**Versão:** 1.0 | **Data:** 2026-04-05 | **Story:** PC-1.5

> Este playbook cobre dois cenários: lead que chega direto no WhatsApp do Mauro (Canal B)
> e lead que veio via handoff da Zenya Vendedora com contexto BANT (Canal B2).
> Salve cada script como resposta rápida no WhatsApp Business para usar com 2 toques.

---

## CANAL B — Lead Frio
*Lead chegou direto no seu WhatsApp. Você não sabe nada sobre ele ainda.*

---

### /abertura-frio
**Quando usar:** primeira mensagem para um lead novo que chegou direto

```
Oi! Vi que você entrou em contato com a Sparkle.
Me conta um pouco — qual é o seu negócio?
```

> Tom: direto, curioso, sem apresentação formal. Não comece com "Olá, sou Mauro da Sparkle..." — isso soa como telemarketing.

---

### /bant-1 — Descobrir a dor
**Quando usar:** após entender o negócio, descobrir o problema real

```
E como vocês atendem os clientes hoje? Principalmente no WhatsApp — consegue dar conta de tudo?
```

> Objetivo: que a pessoa fale sobre mensagens perdidas, demora, atendimento fora do horário.

---

### /bant-2 — Quantificar a dor
**Quando usar:** após ouvir a dor, calibrar urgência

```
Você chega a perder vendas por isso? Tipo cliente que manda mensagem e some porque demorou a resposta?
```

> Objetivo: que a pessoa calcule, mesmo que de forma intuitiva, o impacto real.

---

### /bant-3 — Confirmar decisão + urgência
**Quando usar:** após confirmar a dor, fechar o diagnóstico

```
Você é quem cuida dessa parte do negócio? E tem alguma data importante chegando — tipo uma promoção, evento, data sazonal?
```

> Objetivo: confirmar que é o decisor e criar urgência natural (não fabricada).

---

### /cta-demo
**Quando usar:** lead qualificado — dor clara, é o decisor, tem urgência

```
Faz sentido você ver como a Zenya ficaria configurada pro seu negócio especificamente.
É uma conversa rápida — 20 minutos. Eu mostro ao vivo, com o seu nicho.

Segue o link pra você escolher o horário: [CALENDLY_LINK]
```

> Substitua [CALENDLY_LINK] pelo link real antes de ativar.

---

### /encerra-elegante
**Quando usar:** lead claramente fora do ICP (não usa WhatsApp como canal principal, empresa muito grande, não é o decisor)

```
Entendo — parece que o momento não é esse ainda.
Se um dia fizer sentido revisitar, pode me chamar aqui. Boa sorte no negócio! 🙂
```

> Nunca pressione. Nunca crie urgência falsa. Lead não-ICP hoje pode ser ICP em 3 meses.

---

### Respostas para as 5 objeções mais comuns

**"É caro"**
```
Depende do quanto você está perdendo hoje. Me conta: quantas mensagens por dia ficam sem resposta?
[calcule ao vivo: mensagens × % que vira venda × ticket médio × 22 dias]
Normalmente a Zenya se paga no primeiro mês.
```

**"Preciso pensar"**
```
Faz sentido. O que falta pra você ter certeza? Posso te ajudar com essa parte agora.
```

**"Já tenho um bot"**
```
Qual o maior problema do seu bot atual?
A maioria dos bots é fluxo engessado — a Zenya entende o contexto da conversa, não só palavras-chave.
```

**"Meus clientes não gostam de robô"**
```
Faz sentido a preocupação. Mas olha como a nossa conversa aqui está sendo — você percebeu que estava falando com uma IA?
A Zenya é assim com os clientes do seu negócio também.
```

**"E se der problema?"**
```
A Zenya tem handoff humano — quando ela não sabe ou o cliente precisa de você, ela te chama.
Você não some do atendimento, só não fica mais sozinho nele.
```

---

## CANAL B2 — Lead Quente (Handoff da Zenya)
*Você recebeu uma notificação da Friday com contexto BANT do lead. Não comece do zero.*

---

### Como ler a notificação da Friday

A Friday vai te mandar algo assim:
```
🔥 Lead quente: [NOME]
Score: alto
Nicho: [ex: confeitaria artesanal]
Dor: [ex: perde 30 msgs/dia fora do horário]
→ Chatwoot: [link]
```

**Use esses dados na abertura.** Não pergunte o que a Friday já te disse.

---

### /abertura-handoff
**Quando usar:** primeiro contato com lead que veio via handoff da Zenya Vendedora

```
Oi [NOME], aqui é o Mauro da Sparkle.
A Zenya me avisou que você quer conversar sobre [DOR IDENTIFICADA].
Posso te ajudar com isso agora — tem 20 minutos?
```

> Substitua [NOME] e [DOR IDENTIFICADA] com o que chegou na notificação da Friday.
> Tom: direto, pessoal, mostra que você leu o contexto. Não repita perguntas que a Zenya já fez.

---

### Fluxo Canal B2 (máximo 3 mensagens até o CTA)

```
Mensagem 1: /abertura-handoff (com contexto preenchido)
Mensagem 2: "Pelo que você conversou com a Zenya, parece que [resumo da dor]. Certo?"
             → Confirma entendimento, não requalifica
Mensagem 3: /cta-demo
```

Se o lead já está quente o suficiente (respondeu a Zenya e pediu para falar com alguém), você pode ir direto do M1 para M3.

---

### /d0-proposta
**Quando usar:** após demo realizada, enviar proposta em até 2 horas

```
[NOME], obrigado pela conversa de hoje!

Conforme conversamos, aqui está o resumo:

Problema identificado: [DOR ESPECÍFICA]
O que a Zenya resolve: [2-3 capacidades relevantes para o nicho]
Resultado esperado: [se calculou ROI ao vivo, coloque aqui]

Investimento: R$[VALOR]/mês
Inclui: configuração completa, soul prompt personalizado, suporte nos primeiros 30 dias.

Para confirmar, é só responder "topei" aqui mesmo ou assinar pelo link: [LINK_PROPOSTA]

Prazo para essa condição: 48 horas.

Qualquer dúvida, pode me chamar aqui! 🙂
```

> Preencha os campos em colchetes antes de enviar. Nunca envie o template sem personalizar.

---

## Etiquetas do Pipeline (configurar no WhatsApp Business)

| Etiqueta | Cor | Quando aplicar |
|----------|-----|----------------|
| 🔵 Novo Lead | Azul | Primeiro contato recebido |
| 🟡 Qualificado | Amarelo | Passou no BANT (score Alto ou Médio) |
| 🟠 Demo Agendada | Laranja | Link Calendly enviado e confirmado |
| 🔴 Proposta Enviada | Vermelho | /d0-proposta enviado |
| 🟢 Cliente | Verde | Pagamento confirmado |
| ⚫ Perdido | Cinza | Desistiu ou não é ICP |

**Como atualizar:** no WhatsApp Business, pressione e segure o contato → Etiqueta → selecione a nova etiqueta. Menos de 5 segundos.

---

## Resumo das Respostas Rápidas (8 itens)

| Comando | Uso |
|---------|-----|
| `/abertura-frio` | Primeiro contato Canal B |
| `/bant-1` | Descobrir dor |
| `/bant-2` | Quantificar dor |
| `/bant-3` | Confirmar decisão + urgência |
| `/abertura-handoff` | Primeiro contato Canal B2 (preencher [NOME] e [DOR]) |
| `/cta-demo` | Convite para demo (preencher [CALENDLY_LINK]) |
| `/encerra-elegante` | Encerramento para não-ICP |
| `/d0-proposta` | Proposta pós-demo (preencher todos os campos) |

---

## Como configurar no WhatsApp Business

1. Abra o WhatsApp Business → ⋮ → Ferramentas Comerciais → Respostas Rápidas
2. Para cada item acima: toque em `+` → cole o texto → defina o atalho (ex: `abertura-frio`)
3. Para usar: em qualquer conversa, digite `/` → selecione o atalho
4. Para etiquetas: ⋮ → Ferramentas Comerciais → Etiquetas → crie as 6 etiquetas com as cores indicadas

---

## PROPOSTA D0 — Template padrão
*Story PC-1.5b — aprovado por Mauro 2026-04-05*

> Enviada automaticamente pelo follow-up PC-1.6 até 2h após a demo.
> Os campos `[ENTRE COLCHETES]` são preenchidos pelo sistema com dados do lead.
> Antes de enviar manualmente: revise o VALOR e ajuste se necessário.

### /d0-proposta

```
Oi [NOME] 👋

Depois da nossa conversa, preparei um resumo de como posso ajudar.

🔍 *O que identificamos:*
[PROBLEMA — gerado a partir da dor identificada no BANT]

✅ *O que está incluído:*
• Zenya configurada para o seu negócio ([TIPO_NEGOCIO])
• Atendimento automático 24h no WhatsApp
• Agendamento/triagem de clientes
• Handoff para você quando necessário
• Suporte e ajustes nos primeiros 30 dias

💰 *Investimento:* R$497/mês
Sem taxa de setup. Sem contrato mínimo.

Para confirmar, é só responder *"topo"* aqui mesmo 🙂
```

**Ajustes manuais antes de enviar:**
- Valor padrão R$497 — altere se o lead for plano diferente (Prime = R$897)
- Revise o bloco "O que identificamos" — o sistema gera, você valida

---

*Playbook criado por @pm (Morgan) | PC-1.5 aprovado por Mauro 2026-04-05 | PC-1.5b (proposta) aprovado por Mauro 2026-04-05*
