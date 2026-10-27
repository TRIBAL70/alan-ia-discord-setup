import os
import asyncio
import re
import traceback
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
ALIASES = {
 "boas-vindas":["boas-vindas"],
 "regras":["regras"],
 "anúncios":["avisos","anúncios"],
 "escolher-cargos":["cargos","escolher-cargos"],
 "chat-geral":["chat-geral","geral","bate-papo"],
 "ideias-e-sugestões":["sugestões","ideias-e-sugestões"],
 "dúvidas":["dúvidas","suporte"],
 "equipe":["staff-discussão","staff-discussao"],
 "Bate-papo Tech":["call livre"],
 "Programando juntos":["geral-1"],
 "Laboratório de IA":["geral-2"],
}
def canonical(name):
 clean = re.sub(r"[^\\w\\s-]+", " ", name.casefold())
 return re.sub(r"\\s+", " ", clean).strip().replace(" ", "-")

class Setup(discord.Client):
 def __init__(self):
  super().__init__(intents=discord.Intents(guilds=True))
  self.done=False
  self.failed=False
 async def on_ready(self):
  if self.done:return
  self.done=True
  try: await self.configure()
  except Exception:
   self.failed=True
   traceback.print_exc()
  finally: await self.close()
 async def configure(self):
  guild=self.get_guild(GUILD_ID)
  if guild is None: raise RuntimeError("Alan IA não encontrou o servidor. Verifique a instalação e o ID.")
  member=guild.me
  if not(member.guild_permissions.manage_channels and member.guild_permissions.manage_roles):
   raise RuntimeError("Bot precisa de Gerenciar Canais e Gerenciar Cargos.")
  roles={}
  problems=[]
  for name,colour in ROLES:
   role=discord.utils.get(guild.roles,name=name)
   if role is None:
    role=await guild.create_role(name=name,colour=discord.Colour(colour),permissions=discord.Permissions.none(),reason="Instalação ALUNOS DEV-CLUB")
   roles[name]=role
  for title,items in GROUPS:
   try:
    await self.setup_category(guild,member,roles,title,items,problems)
   except Exception as ex:
    problems.append(f"Categoria {title}: {type(ex).__name__}: {ex}")
    print("FALHA CATEGORIA",title,repr(ex),flush=True)
  if problems:
   print("RESUMO DE FALHAS:",len(problems),flush=True)
   for entry in problems: print("PENDENTE:",entry,flush=True)
   raise RuntimeError(f"Instalação parcialmente concluída: {len(problems)} problemas. Consulte os logs.")
  print("Concluído: 7 categorias, 26 canais previstos e 7 cargos. Nenhuma mensagem apagada.",flush=True)
 async def setup_category(self,guild,member,roles,title,items,problems):
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
    try:
     await self.setup_channel(guild,category,title,item)
    except Exception as ex:
     problems.append(f"Canal {item} / {title}: {type(ex).__name__}: {ex}")
     print("FALHA CANAL",title,item,repr(ex),flush=True)
 async def setup_channel(self,guild,category,title,item):
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
if not TOKEN: raise SystemExit("Crie o segredo DISCORD_BOT_TOKEN no GitHub Actions.")
app=Setup()
app.run(TOKEN)
if app.failed:
 raise SystemExit('FALHA: instalação incompleta — verifique o traceback acima.')
