# ALUNOS DEV-CLUB — configuração automática

Servidor Discord: `1246627128074567680`. Bot Alan IA: `1564445890725281992`.

Este instalador reorganiza canais existentes quando reconhece nomes equivalentes e cria os canais faltantes. Não apaga mensagens nem atribui cargos elevados a membros automaticamente. A categoria ADMINISTRAÇÃO é restrita por permissões.

## Executar

1. No Discord Developer Portal, instale o bot no servidor com permissões **Gerenciar Canais**, **Gerenciar Cargos** e **Ver Canais**.
2. No GitHub, acesse **Settings → Secrets and variables → Actions → New repository secret**.
3. Nome: `DISCORD_BOT_TOKEN`. Valor: token privado do seu bot, copiado do portal (não compartilhe esse valor em mensagens, arquivos ou prints).
4. Acesse **Actions → Configurar servidor Discord → Run workflow**.
5. Confira o log da execução.

O bot aparece offline fora da execução do fluxo. A IA conversacional e os tickets necessitam de serviços/bots adicionais. O GitHub Actions serve para configuração pontual, **não** para hospedagem 24h do bot.
