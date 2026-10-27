# Alan IA — Hospedagem permanente

O projeto contém um bot Gateway de Discord que precisa rodar continuamente. GitHub Actions não serve para hospedagem 24h.

## Render (worker Python)

1. Crie ou conecte uma conta em https://dashboard.render.com/.
2. **New → Blueprint** e conecte `TRIBAL70/alan-ia-discord-setup`.
3. O Render reconhecerá `render.yaml`, criando um **Background Worker**. Pode exigir plano pago; confira o preço antes de confirmar.
4. Na etapa das variáveis, use **DISCORD_BOT_TOKEN**: copie o valor no Discord Developer Portal para o Render, diretamente. Não envie por chat, arquivo ou commit.
5. Para ativar `/perguntar`, adicione `OPENAI_API_KEY` manualmente em **Environment**; essa API tem cobrança própria, separada do ChatGPT Plus.
6. Ative o serviço. Nos logs, procure `Alan IA conectado` e `comandos sincronizados`. No Discord, teste `/ping` e `/ajuda`, depois `/ticket`.

**Importante:** o segredo DISCORD_BOT_TOKEN do GitHub Actions **não** é copiado automaticamente para a Render.

O bot usa commands slash específicos do servidor `1246627128074567680`. Não requer Message Content Intent.

Configure **uma única instância** de bot para evitar múltiplas sessões Gateway, e evite usar `instalar.py` como processo contínuo.

**Segurança de tickets:** `/fechar` exclui o canal e suas mensagens. Salve o que for necessário antes de fechar. Confirme que o bot tem permissão **Gerenciar Canais**, **Ver Canais**, **Enviar Mensagens** e **Ler Histórico** e que a categoria SUPORTE existe.
