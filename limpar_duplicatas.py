"""Remove somente 7 canais duplicados vazios auditados em 2026-10-27.
Revalida canais, permissões, histórico e threads antes de excluir.
"""
import os
import asyncio
import discord

GUILD_ID=1246627128074567680
TOKEN=os.environ.get("DISCORD_BOT_TOKEN")
# (preservar_id, excluir_id)
PAIRS=[
 (1564597192642002995,1564603241659113627), # ideias
 (1564597103345401929,1564603239079608350), # projetos
 (1564597107061424150,1564603244590927932), # chat-ia
 (1564597110010028102,1564603247598112839), # comandos
 (1564597112916672602,1564603253486784553), # novidades
 (1564597116871901234,1564603256125263942), # desenvolvimento
 (1564597119468445707,1564603261401563136), # python
]

def normalize(name):
 import unicodedata,re
 name=unicodedata.normalize("NFKC",name).casefold()
 return re.sub(r"\s+","-",re.sub(r"[^\w\s-]"," ",name)).strip("-")

async def empty(channel):
 try:
  if [m async for m in channel.pins()]: return False,"possui mensagens fixadas"
  if [m async for m in channel.history(limit=1)]:return False,"possui mensagens"
  if channel.threads:return False,"possui threads ativas"
  # An archived thread (public or private) must not be silently destroyed.
  try:
   async for thread in channel.archived_threads(limit=1,private=False):
    return False,"possui threads públicas arquivadas"
   if not channel.permissions_for(channel.guild.me).manage_threads:
    return False,"bot sem Gerenciar Threads neste canal; não é possível verificar threads privadas"
   async for thread in channel.archived_threads(limit=1,private=True):
    return False,"possui threads privadas arquivadas"
  except discord.Forbidden:
   return False,"não pode verificar threads arquivadas"
  except discord.HTTPException as exc:
   return False,f"falha ao verificar threads: {exc.status}"
  return True,"vazio"
 except (discord.Forbidden,discord.HTTPException) as exc:
  return False,f"não foi possível verificar histórico/pins: {exc}"

class Cleanup(discord.Client):
 def __init__(self):
  super().__init__(intents=discord.Intents(guilds=True))
  self.failures=[]
  self.deleted=0
 async def on_ready(self):
  try:
   guild=self.get_guild(GUILD_ID)
   if not guild:raise RuntimeError("Bot não está no servidor especificado.")
   if not guild.me.guild_permissions.manage_channels:
    raise RuntimeError("Bot precisa de Gerenciar Canais.")
   for keep_id,delete_id in PAIRS:
    try:
     keep=await guild.fetch_channel(keep_id)
     target=await guild.fetch_channel(delete_id)
     if not (isinstance(keep,discord.TextChannel) and isinstance(target,discord.TextChannel)):
      print("IGNORADO",delete_id,"tipo inesperado",flush=True);continue
     if keep.category_id!=target.category_id or normalize(keep.name)!=normalize(target.name):
      print("IGNORADO",delete_id,"categoria ou nome não coincide mais",flush=True);continue
     if target.created_at<=keep.created_at:
      print("IGNORADO",delete_id,"não é a cópia mais nova",flush=True);continue
     if keep.overwrites!=target.overwrites:
      print("IGNORADO",delete_id,"permissões diferentes; revisar manualmente",flush=True);continue
     can_delete,reason=await empty(target)
     if not can_delete:
      print("PRESERVADO",delete_id,reason,flush=True);continue
     print("EXCLUINDO APENAS DUPLICATA VAZIA",delete_id,"mantendo",keep_id,flush=True)
     await target.delete(reason="Limpeza autorizada de duplicata vazia, após auditoria e rechecagem")
     self.deleted+=1
     await asyncio.sleep(1)
    except discord.NotFound:
     print("JÁ NÃO EXISTE",delete_id,flush=True)
    except Exception as exc:
     print("FALHA AO PROCESSAR",delete_id,repr(exc),flush=True)
     self.failures.append(delete_id)
   print(f"RESUMO: {self.deleted} duplicatas removidas; {len(self.failures)} erros. Canais originais preservados.",flush=True)
  except Exception as exc:
   print("ERRO GERAL",repr(exc),flush=True)
   self.failures.append("geral")
  finally:await self.close()
if not TOKEN:raise SystemExit("Configure segredo DISCORD_BOT_TOKEN.")
app=Cleanup()
app.run(TOKEN)
if app.failures:raise SystemExit("Limpeza parcial: revisar registros.")

# Reexecução autorizada após habilitar Gerenciar Threads no cargo do bot.
