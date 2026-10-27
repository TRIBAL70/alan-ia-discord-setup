import os
import asyncio
import re
import discord

GUILD_ID = 1246627128074567680
TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
GROUPS = [
 ("『📌』➤ INFORMAÇÕES", ["👋|boas-vindas","📜|regras","📢|anúncios","🎭|escolher-cargos"]),
 ("『💬』➤ COMUNIDADE", ["💬|chat-geral","🤝|apresentações","📸|projetos-da-galera","💡|ideias-e-sugestões"]),
 ("『🤖』➤ INTELIGÊNCIA ARTIFICIAL", ["🧠|chat-com-ia","🤖|comandos-dos-bots","⚙️|automações","📰|novidades-ia"]),
 ("『💻』➤ PROGRAMAÇÃO", ["🌐|desenvolvimento-web","📱|aplicativos","🐍|python-e-javascript","🆘|ajuda-com-código"]),
 ("『🎫』➤ SUPORTE", ["🎟️|abrir-ticket","❓|dúvidas","⭐|avaliações"]),
 ("『🔊』➤ SALAS DE VOZ", ["🎙️|Bate-papo Tech","💻|Programando juntos","🤖|Laboratório de IA"]),
 ("『🔐』➤ ADMINISTRAÇÃO", ["🛡️|equipe","📋|logs","🚨|alertas","📊|relatórios"])
]
ROLES = [("『👑』➤ Fundador",0xF5C542),("『🛡️』➤ Administrador",0xED4245),
 ("『🔧』➤ Moderador",0x5865F2),("『🤖』➤ Bot IA",0x9B59B6),
 ("『💎』➤ VIP",0x00D5FF),("『💻』➤ Desenvolvedor",0x2ECC71),("『👤』➤ Membro",0x95A5A6)]
ALIASES = {"boas-vindas":["boas-vindas","『❗』boas-vindas"],
 "anúncios":["anúncios","avisos","『❗』avisos"],
 "escolher-cargos":["escolher-cargos","cargos","『❗』cargos"]}
def canonical(name):
 clean = re.sub(r"[^\\w\\s-]+", " ", name.casefold())
 return re.sub(r"\\s+", " ", clean).strip().replace(" ", "-")
class Setup(discord.Client):
 def __init__(self):
  super().__init__(intents=discord.Intents(guilds=True))
  self.done=False
 async def on_ready(self):
  if self.done:return
  self.done=True
  try: await self.configure()
  finally: await self.close()
 async def configure(self):
  guild=self.get_guild(GUILD_ID)
  if guild is None: raise RuntimeError("Alan IA não encontrou o servidor. Verifique a instalação e o ID.")
  member=guild.me
  if not(member.guild_permissions.manage_channels and member.guild_permissions.manage_roles):
   raise RuntimeError("Bot precisa de Gerenciar Canais e Gerenciar Cargos.")
  roles={}
  for name,colour in ROLES:
   role=discord.utils.get(guild.roles,name=name)
   if role is None:
    role=await guild.create_role(name=name,colour=discord.Colour(colour),permissions=discord.Permissions.none(),reason="Instalação ALUNOS DEV-CLUB")
   roles[name]=role
  for title,items in GROUPS:
   private="ADMINISTRAÇÃO" in title
   category=discord.utils.get(guild.categories,name=title)
   if category is None and title.endswith("INFORMAÇÕES"):
    category=next((c for c in guild.categories if "boas-vindas" in c.name.casefold() and "informa" in c.name.casefold()),None)
    if category:
     await category.edit(name=title,reason="Reaproveitar categoria existente")
   if category is None:
    perms={}
    if private:
     perms[guild.default_role]=discord.PermissionOverwrite(view_channel=False)
     perms[member]=discord.PermissionOverwrite(view_channel=True)
     for role_name in ["『👑』➤ Fundador","『🛡️』➤ Administrador","『🔧』➤ Moderador"]:
      perms[roles[role_name]]=discord.PermissionOverwrite(view_channel=True)
    category=await guild.create_category(title,overwrites=perms,reason="Instalação ALUNOS DEV-CLUB")
   print("CATEGORIA", title, flush=True)
   if private:
    await category.set_permissions(guild.default_role,view_channel=False)
    await category.set_permissions(member,view_channel=True)
    for role_name in ["『👑』➤ Fundador","『🛡️』➤ Administrador","『🔧』➤ Moderador"]:
     await category.set_permissions(roles[role_name],view_channel=True)
   for item in items:
    emoji,base=item.split("|",1)
    desired=f"『{emoji}』» {base}"
    voice="SALAS DE VOZ" in title
    kind=discord.VoiceChannel if voice else discord.TextChannel
    aliases=[base,*ALIASES.get(base,[])]
    existing=next((c for c in guild.channels if isinstance(c,kind) and c.name==desired),None)
    if existing is None:
     choices={canonical(a) for a in aliases}
     existing=next((c for c in guild.channels if isinstance(c,kind) and (canonical(c.name) in choices or any(canonical(c.name).endswith("-"+x) for x in choices))),None)
    if existing:
     if existing.category_id!=category.id or existing.name!=desired:
      await existing.edit(name=desired,category=category,sync_permissions=private,reason="Organização de canais")
     elif private:
      await existing.edit(sync_permissions=True,reason="Proteção da administração")
    elif voice:
     await guild.create_voice_channel(desired,category=category,reason="Instalação ALUNOS DEV-CLUB")
    else:
     await guild.create_text_channel(desired,category=category,reason="Instalação ALUNOS DEV-CLUB")
    print("OK",desired,flush=True)
    await asyncio.sleep(0.4)
  print("Concluído: 7 categorias, 26 canais previstos e 7 cargos. Nenhuma mensagem apagada.",flush=True)
if not TOKEN: raise SystemExit("Crie o segredo DISCORD_BOT_TOKEN no GitHub Actions.")
Setup().run(TOKEN)
