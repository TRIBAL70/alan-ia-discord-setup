import os
import asyncio
import discord

GUILD_ID=1246627128074567680
TOKEN=os.getenv("DISCORD_BOT_TOKEN")
TARGET=["chat-com-ia","desenvolvimento-web","boas-vindas"]
class Verify(discord.Client):
 def __init__(self):
  super().__init__(intents=discord.Intents(guilds=True))
  self.failed=False
 async def on_ready(self):
  try:
   guild=self.get_guild(GUILD_ID)
   if guild is None:
    raise RuntimeError("Bot não está no servidor configurado.")
   me=guild.me
   permissions=me.guild_permissions
   print("BOT:",str(me),flush=True)
   print("CARGOS BOT:",", ".join(r.name for r in me.roles),flush=True)
   print("CARGO MAIS ALTO BOT:",me.top_role.name,flush=True)
   print("PERMISSÃO GERENCIAR CANAIS:", permissions.manage_channels,flush=True)
   print("PERMISSÃO GERENCIAR CARGOS:", permissions.manage_roles,flush=True)
   print("PERMISSÃO ADMINISTRADOR:", permissions.administrator,flush=True)
   channels=await guild.fetch_channels()
   categories=[c for c in channels if isinstance(c,discord.CategoryChannel)]
   print(f"Servidor: {guild.name} (ID {guild.id})")
   print(f"Categorias encontradas: {len(categories)}; canais encontrados: {len(channels)}")
   for c in categories:
    print(f"CATEGORIA: {c.name}")
   missing=[]
   for key in TARGET:
    matches=[c for c in channels if key.casefold() in c.name.casefold()]
    print(f"BUSCA {key}: "+(", ".join(f'{c.name} [{c.id}]' for c in matches) or "NÃO ENCONTRADO"))
    if not matches:missing.append(key)
   if missing:print("CANAIS FALTANDO:",", ".join(missing),flush=True)
   if not permissions.manage_channels or not permissions.manage_roles:
    raise RuntimeError("PERMISSÕES INSUFICIENTES: ajuste o cargo Alan IA no Discord.")
   if missing:print("Falta executar instalador para criar canais; permissões globais estão presentes.",flush=True)
   print("VERIFICAÇÃO OK")
  except Exception as e:
   print("ERRO DIAGNÓSTICO:",repr(e),flush=True)
   self.failed=True
  finally:
   await self.close()
if not TOKEN:raise SystemExit("Segredo DISCORD_BOT_TOKEN ausente.")
app=Verify()
app.run(TOKEN)
if app.failed:raise SystemExit("Diagnóstico falhou: verifique permissões e registros")
