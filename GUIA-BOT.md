# Alan IA — Ativação do bot

**Discord:** servidor 1246627128074567680 · aplicativo 1564445890725281992.

## O que funciona
- /ajuda, /ping, /ticket, /fechar: bot rodando em hospedagem Python.
- /perguntar: bot rodando **e** `OPENAI_API_KEY` configurada; uso da API pode ter custo.

## Instalação inicial
O workflow GitHub Actions `Configurar servidor Discord` instala categorias, canais e cargos **uma vez**. Não liga o Alan IA 24h.

## Hospedagem contínua
Em qualquer serviço confiável com processo Python persistente (ou PC que fique ligado):
1. Instale Python 3.12.
2. Execute `pip install -r requirements-bot.txt`.
3. Cadastre variáveis privadas `DISCORD_BOT_TOKEN` e, opcionalmente, `OPENAI_API_KEY` no painel do provedor.
4. Execute `python bot.py`.

**Nunca** envie tokens pelo chat, publique arquivos .env reais ou faça commit de chaves. Token Discord: Developer Portal > Bot. A API do OpenAI é separada do ChatGPT Plus. Não use GitHub Actions como hospedagem contínua.

## Cargos
Os cargos são criados **sem** permissões administrativas por padrão. Atribua funções manualmente pela interface do Discord e restrinja quem pode gerenciar permissões.

## Segurança dos tickets
Cada ticket cria um canal privado para solicitante, moderação e bot. /fechar exclui o canal e as mensagens nele; salve dados necessários antes de fechar. Use respeitando a privacidade dos membros.
