"""Alan IA — comandos slash, tickets e IA opcional. Python 3.12."""
import os
import logging
import re
import discord
from discord import app_commands

logging.basicConfig(level=logging.INFO)
TOKEN=os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID=1246627128074567680
AI_KEY=os.getenv("OPENAI_API_KEY")
AI_MODEL=os.getenv("OPENAI_MODEL","gpt-4.1-mini")
intents=discord.Intents.default()
client=discord.Client(intents=intents)
tree=app_commands.CommandTree(client)

@client.event
async def on_ready():
    guild=discord.Object(id=GUILD_ID)
    try:
        await tree.sync(guild=guild)
        print(f"Alan IA conectado como {client.user}; comandos sincronizados")
    except Exception:
        logging.exception("Erro ao sincronizar comandos")

def server_only(interaction):
    return interaction.guild_id==GUILD_ID

@tree.command(name="ajuda",description="Ver comandos do Alan IA",guild=discord.Object(id=GUILD_ID))
async def ajuda(interaction:discord.Interaction):
    await interaction.response.send_message(
        "**Alan IA** 🤖\n/ajuda — comandos\n/perguntar — tirar dúvida com IA (exige chave da API)\n/ticket — abrir atendimento privado\n/fechar — encerrar ticket\n/ping — verificar funcionamento",
        ephemeral=True)

@tree.command(name="ping",description="Verificar se o bot está online",guild=discord.Object(id=GUILD_ID))
async def ping(interaction:discord.Interaction):
    await interaction.response.send_message("🏓 Alan IA online!",ephemeral=True)

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

if __name__=="__main__":
    if not TOKEN:raise SystemExit("Configure DISCORD_BOT_TOKEN somente no ambiente seguro de execução.")
    client.run(TOKEN)
