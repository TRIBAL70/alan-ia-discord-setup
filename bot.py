"""Alan IA — comandos slash, tickets e IA opcional. Python 3.12."""
import os
import logging
import re
from urllib.parse import urlsplit
import discord
from discord import app_commands
from welcome_cards import get_background, send_member_welcome, welcome_channel

logging.basicConfig(level=logging.INFO)
TOKEN=os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID=1246627128074567680
GUILD_NICKNAME = "Alan Sky"
AI_KEY=os.getenv("OPENAI_API_KEY")
AI_MODEL=os.getenv("OPENAI_MODEL","gpt-4.1-mini")
class AlanClient(discord.Client):
    async def setup_hook(self):
        flags = self.application.flags
        allowed = flags.gateway_guild_members or flags.gateway_guild_members_limited
        # Client.intents returns a copy; the Gateway reads the state-bound flags.
        self._connection._intents.members = allowed
        if not allowed:
            logging.warning("Boas-vindas automáticas aguardam Server Members Intent no Discord.")


intents = discord.Intents.default()
client = AlanClient(
    intents=intents,
    chunk_guilds_at_startup=False,
)
tree=app_commands.CommandTree(client)

@client.event
async def on_member_join(member):
    if member.guild.id == GUILD_ID:
        await send_member_welcome(member)



async def restrict_meeting_summary(server):
    channel_id = 1564603227255734302
    channel = await server.fetch_channel(channel_id)
    if not isinstance(channel, discord.TextChannel) or not channel.name.endswith("resumo-reunião"):
        raise ValueError("Canal de resumo não confere com o servidor e o nome esperados.")

    moderators = [role for role in server.roles if role.name in ("『🔧』➤ Moderador", "Moderador")]
    if len(moderators) != 1:
        raise ValueError("Não foi possível identificar um único cargo Moderador.")
    moderator = moderators[0]
    everyone = server.default_role
    post_fields = ("send_messages", "send_messages_in_threads", "create_public_threads", "create_private_threads")
    before = channel.overwrites
    after = {role: discord.PermissionOverwrite.from_pair(*rule.pair()) for role, rule in before.items()}
    for target, rule in after.items():
        if target.id not in (moderator.id, everyone.id):
            for name in post_fields:
                if getattr(rule, name) is True:
                    setattr(rule, name, None)
    baseline = after.setdefault(everyone, discord.PermissionOverwrite())
    for name in post_fields:
        setattr(baseline, name, False)
    mod_rule = after.setdefault(moderator, discord.PermissionOverwrite())
    previous_mod_permissions = channel.permissions_for(moderator)
    mod_rule.send_messages = True
    for name in post_fields[1:]:
        if getattr(previous_mod_permissions, name):
            setattr(mod_rule, name, True)
    after = {role: rule for role, rule in after.items() if not rule.is_empty()}

    if after != before:
        await channel.edit(overwrites=after, reason="Somente o cargo Moderador pode postar em resumo-reunião")
    verified = await server.fetch_channel(channel_id)
    expected = verified.overwrites_for(everyone)
    other_allows = any(
        target.id not in (everyone.id, moderator.id) and any(getattr(rule, name) is True for name in post_fields)
        for target, rule in verified.overwrites.items()
    )
    if any(getattr(expected, name) is not False for name in post_fields) or other_allows:
        raise ValueError("A restrição do canal não foi confirmada na leitura do Discord.")
    if not verified.permissions_for(moderator).send_messages:
        raise ValueError("O cargo Moderador ainda não consegue postar no canal.")
    visibility_unchanged = all(
        pair.view_channel == verified.overwrites_for(role).view_channel
        and pair.read_message_history == verified.overwrites_for(role).read_message_history
        for role, pair in before.items()
    )
    if not visibility_unchanged:
        raise ValueError("As permissões de leitura não conferem.")
    logging.info("RESUMO_REUNIAO confirmado: somente Moderador e exceções nativas do Discord; leitura preservada; bot_pode_postar=%s.",
                 verified.permissions_for(server.me).send_messages)


@client.event
async def on_ready():
    server = client.get_guild(GUILD_ID)
    channel = welcome_channel(server)
    logging.info("Boas-vindas: eventos=%s, canal=%s.", client.intents.members, channel is not None)
    if server is not None and server.me is not None:
        try:
            bot_member = server.me
            if bot_member.display_name != GUILD_NICKNAME:
                await bot_member.edit(nick=GUILD_NICKNAME, reason="Nome solicitado para o bot da Irmandade")
                bot_member = await server.fetch_member(bot_member.id)
            logging.info("Nome de exibição do bot na Irmandade: %s.", bot_member.display_name)
        except discord.HTTPException:
            logging.exception("Não foi possível atualizar o nome de exibição na Irmandade.")
    if server is not None:
        try:
            await restrict_meeting_summary(server)
        except (discord.HTTPException, ValueError):
            logging.exception("RESUMO_REUNIAO: não foi possível aplicar a restrição.")
    guild=discord.Object(id=GUILD_ID)
    try:
        await tree.sync(guild=guild)
        print(f"Alan IA conectado como {client.user}; comandos sincronizados")
    except Exception:
        logging.exception("Erro ao sincronizar comandos")
    if client.intents.members and channel is not None:
        try:
            await get_background()
            logging.info("GIF de fundo das boas-vindas carregado.")
        except Exception:
            logging.exception("Não foi possível preparar o GIF das boas-vindas.")

def server_only(interaction):
    return interaction.guild_id==GUILD_ID

@tree.command(name="ajuda",description="Ver comandos do Alan IA",guild=discord.Object(id=GUILD_ID))
async def ajuda(interaction:discord.Interaction):
    await interaction.response.send_message(
        "**Alan Sky** 🤖\n/ajuda — comandos\n/perguntar — tirar dúvida com IA (exige chave da API)\n/ticket — abrir atendimento privado\n/fechar — encerrar ticket\n/ping — verificar funcionamento\n/mensagem — montar mensagens com imagem ou GIF\n/boas-vindas — montar uma saudação personalizada",
        ephemeral=True)

@tree.command(name="ping",description="Verificar se o bot está online",guild=discord.Object(id=GUILD_ID))
async def ping(interaction:discord.Interaction):
    await interaction.response.send_message("🏓 Alan Sky online!",ephemeral=True)

@tree.command(name="ticket",description="Criar atendimento privado",guild=discord.Object(id=GUILD_ID))
@app_commands.describe(assunto="Descreva resumidamente sua solicitação")
async def ticket(interaction:discord.Interaction,assunto:str):
    guild=interaction.guild
    if guild is None:return await interaction.response.send_message("Use no servidor.",ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    prefix=f"ticket-{interaction.user.id}"
    existing=discord.utils.get(guild.text_channels,name=prefix)
    if existing:return await interaction.followup.send(f"Você já tem um ticket: {existing.mention}",ephemeral=True)
    category=next((c for c in guild.categories if "SUPORTE" in c.name.upper()),None)
    if not category:
        return await interaction.followup.send("Categoria SUPORTE indisponível. Execute o instalador.",ephemeral=True)
    overwrites={
        guild.default_role:discord.PermissionOverwrite(view_channel=False),
        interaction.user:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),
        guild.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,manage_channels=True)
    }
    for role in guild.roles:
        if any(word in role.name.lower() for word in ("moderador","administrador","fundador")):
            overwrites[role]=discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)
    try:
        channel=await guild.create_text_channel(prefix,category=category,overwrites=overwrites,
           topic=f"Solicitante: {interaction.user.id}; Assunto: {assunto[:150]}",reason="Ticket solicitado")
        await channel.send(f"{interaction.user.mention} abriu atendimento. **Assunto:** {discord.utils.escape_mentions(assunto[:500])}\nUse `/fechar` para encerrar.")
        await interaction.followup.send(f"Seu atendimento foi aberto: {channel.mention}",ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("Faltam permissões para criar canais.",ephemeral=True)

@tree.command(name="fechar",description="Fechar o ticket atual",guild=discord.Object(id=GUILD_ID))
async def fechar(interaction:discord.Interaction):
    channel=interaction.channel
    if not isinstance(channel,discord.TextChannel) or not re.fullmatch(r"ticket-\d+",channel.name):
        return await interaction.response.send_message("Use dentro do canal do ticket.",ephemeral=True)
    owner=int(channel.name.split("-")[1])
    roles=[r.name.lower() for r in interaction.user.roles] if isinstance(interaction.user,discord.Member) else []
    if interaction.user.id!=owner and not any(x in " ".join(roles) for x in ("moderador","administrador","fundador")):
        return await interaction.response.send_message("Apenas o solicitante ou a equipe pode fechar.",ephemeral=True)
    await interaction.response.send_message("Ticket encerrado. Este canal será excluído.")
    await channel.delete(reason=f"Ticket encerrado por {interaction.user}")

@tree.command(name="perguntar",description="Pergunte à inteligência artificial",guild=discord.Object(id=GUILD_ID))
@app_commands.describe(pergunta="Sua dúvida sobre programação, tecnologia ou IA")
async def perguntar(interaction:discord.Interaction,pergunta:app_commands.Range[str,1,1200]):
    await interaction.response.defer(ephemeral=True,thinking=True)
    if not AI_KEY:
        return await interaction.followup.send("A IA ainda não foi ativada. O proprietário deve configurar OPENAI_API_KEY na hospedagem.",ephemeral=True)
    try:
        from openai import AsyncOpenAI
        api=AsyncOpenAI(api_key=AI_KEY,timeout=25)
        response=await api.responses.create(model=AI_MODEL,
           instructions="Você é Alan IA, assistente em português do Brasil da comunidade ALUNOS DEV-CLUB. Responda de maneira objetiva e técnica; não alegue executar ações externas.",
           input=pergunta,max_output_tokens=550)
        answer=response.output_text or "Não consegui gerar uma resposta."
        await interaction.followup.send(answer[:1900],ephemeral=True)
    except Exception:
        logging.exception("Falha na API de IA")
        await interaction.followup.send("Serviço de IA temporariamente indisponível. Tente novamente.",ephemeral=True)


_RICH_MESSAGE_COLORS = {
    "azul": 0x00BFFF,
    "ciano": 0x00DDEB,
    "roxo": 0x8B40FF,
    "verde": 0x39D98A,
    "dourado": 0xD4AF37,
}
_IMAGE_SUFFIXES = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_COLOR_CHOICES = [
    app_commands.Choice(name=color.capitalize(), value=color)
    for color in _RICH_MESSAGE_COLORS
]


async def enviar_mensagem(
    interaction: discord.Interaction,
    titulo: str | None,
    texto: str | None,
    arquivo: discord.Attachment | None,
    link: str | None,
    cor: str,
    publicar: bool,
    canal: discord.TextChannel | None,
) -> None:
    mentions = discord.AllowedMentions.none()
    destino = canal or interaction.channel
    bot = interaction.guild.me if interaction.guild else None

    if not interaction.permissions.manage_messages:
        await interaction.response.send_message(
            "Você precisa da permissão Gerenciar Mensagens.", ephemeral=True
        )
        return
    if publicar and (
        not isinstance(destino, discord.TextChannel)
        or bot is None
        or not isinstance(interaction.user, discord.Member)
        or not destino.permissions_for(interaction.user).view_channel
        or not destino.permissions_for(interaction.user).manage_messages
    ):
        await interaction.response.send_message(
            "Escolha um canal de texto em que você possa gerenciar mensagens.",
            ephemeral=True,
        )
        return
    if publicar:
        permissoes = destino.permissions_for(bot)
        if not (
            permissoes.view_channel
            and permissoes.send_messages
            and permissoes.embed_links
            and (arquivo is None or permissoes.attach_files)
        ):
            await interaction.response.send_message(
                "Preciso de permissão para ver o canal, enviar mensagens e inserir "
                "links. Para arquivos, também preciso de Anexar Arquivos.",
                ephemeral=True,
            )
            return

    titulo = titulo.strip() if titulo else None
    texto = texto.strip() if texto else None
    link = link.strip() if link else None
    if not any((titulo, texto, arquivo, link)):
        await interaction.response.send_message(
            "Adicione um título, texto, imagem ou GIF.", ephemeral=True
        )
        return
    if arquivo and link:
        await interaction.response.send_message(
            "Use um arquivo ou um link de imagem por mensagem.", ephemeral=True
        )
        return
    if link:
        try:
            parsed = urlsplit(link)
            valid_link = (
                parsed.scheme == "https"
                and parsed.hostname
                and parsed.username is None
                and parsed.password is None
                and not any(char.isspace() for char in link)
            )
        except ValueError:
            valid_link = False
        if not valid_link:
            await interaction.response.send_message(
                "Use um link HTTPS direto para a imagem ou o GIF.", ephemeral=True
            )
            return

    tipo = (arquivo.content_type or "").split(";", 1)[0] if arquivo else ""
    if arquivo and (tipo not in _IMAGE_SUFFIXES or arquivo.size > 10 * 1024 * 1024):
        await interaction.response.send_message(
            "Anexe um GIF, PNG, JPG ou WebP de até 10 MiB.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title=titulo, description=texto, color=_RICH_MESSAGE_COLORS[cor]
    )
    await interaction.response.defer(ephemeral=True, thinking=True)
    imagem = None
    try:
        if arquivo:
            nome = f"imagem.{_IMAGE_SUFFIXES[tipo]}"
            imagem = await arquivo.to_file(filename=nome, description=arquivo.description)
            embed.set_image(url=f"attachment://{nome}")
        elif link:
            embed.set_image(url=link)

        argumentos = {"embed": embed, "allowed_mentions": mentions}
        if imagem:
            argumentos["file"] = imagem
        if publicar:
            await destino.send(**argumentos)
        else:
            await interaction.followup.send(ephemeral=True, **argumentos)
    except discord.HTTPException as erro:
        logging.warning("Falha no envio de mensagem personalizada (HTTP %s)", erro.status)
        await interaction.followup.send(
            "O Discord não conseguiu enviar a mensagem. Confira o arquivo, "
            "o link e as permissões do canal.",
            ephemeral=True,
        )
        return
    finally:
        if imagem is not None:
            imagem.close()

    if publicar:
        await interaction.followup.send(
            f"Mensagem publicada em {destino.mention}.", ephemeral=True
        )


@tree.command(
    name="mensagem",
    description="Monte uma mensagem com texto, imagem ou GIF",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.default_permissions(manage_messages=True)
@app_commands.choices(cor=_COLOR_CHOICES)
@app_commands.describe(
    titulo="Título da mensagem",
    texto="Texto da mensagem (aceita Markdown)",
    arquivo="Anexe uma imagem ou GIF animado",
    link="Link HTTPS direto para uma imagem ou GIF",
    cor="Cor da borda",
    publicar="Sim para publicar. Sem marcar, só você vê a prévia.",
    canal="Canal de publicação. Por padrão, usa o canal atual.",
)
async def mensagem(
    interaction: discord.Interaction,
    titulo: app_commands.Range[str, 1, 256] | None = None,
    texto: app_commands.Range[str, 1, 4000] | None = None,
    arquivo: discord.Attachment | None = None,
    link: app_commands.Range[str, 1, 2048] | None = None,
    cor: str = "ciano",
    publicar: bool = False,
    canal: discord.TextChannel | None = None,
) -> None:
    await enviar_mensagem(interaction, titulo, texto, arquivo, link, cor, publicar, canal)


@tree.command(
    name="boas-vindas",
    description="Monte uma mensagem personalizada de boas-vindas",
    guild=discord.Object(id=GUILD_ID),
)
@app_commands.default_permissions(manage_messages=True)
@app_commands.choices(cor=_COLOR_CHOICES)
@app_commands.describe(
    membro="Membro saudado na mensagem. Por padrão, usa seu nome.",
    titulo="Título do cartão de boas-vindas",
    texto="Use {membro} e {servidor} para personalizar",
    arquivo="Anexe uma imagem ou GIF animado",
    link="Link HTTPS direto para uma imagem ou GIF",
    cor="Cor da borda",
    publicar="Sim para publicar. Sem marcar, só você vê a prévia.",
    canal="Canal de publicação. Por padrão, usa o canal atual.",
)
async def boas_vindas(
    interaction: discord.Interaction,
    membro: discord.Member | None = None,
    titulo: app_commands.Range[str, 1, 256] = "👋 Boas-vindas!",
    texto: app_commands.Range[str, 1, 3800] = (
        "Olá, **{membro}**! Boas-vindas ao **{servidor}**!\n"
        "Conte o que você está aprendendo e compartilhe seus projetos com a comunidade."
    ),
    arquivo: discord.Attachment | None = None,
    link: app_commands.Range[str, 1, 2048] | None = None,
    cor: str = "roxo",
    publicar: bool = False,
    canal: discord.TextChannel | None = None,
) -> None:
    nome = discord.utils.escape_markdown((membro or interaction.user).display_name)
    servidor = discord.utils.escape_markdown(interaction.guild.name)
    texto = re.sub(
        r"\{(membro|servidor)\}",
        lambda token: nome if token[1] == "membro" else servidor,
        texto,
    )[:4096]
    await enviar_mensagem(interaction, titulo, texto, arquivo, link, cor, publicar, canal)


if __name__=="__main__":
    if not TOKEN:raise SystemExit("Configure DISCORD_BOT_TOKEN somente no ambiente seguro de execução.")
    client.run(TOKEN)
