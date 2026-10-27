import os
import asyncio
import discord

GUILD_ID=1246627128074567680
TOKEN=os.getenv("DISCORD_BOT_TOKEN")
TARGET=["chat-com-ia","desenvolvimento-web","boas-vindas"]
class Verify(discord.Client):
 def __init__(self):
  super().__init__(intents=discord.Intents(guilds=True))
 async def on_ready(self):
  try:
   guild=self.get_guild(GUILD_ID)
   if guild is None:
    raise RuntimeError("Bot não está no servidor configurado.")
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
   if missing:raise RuntimeError("Canais não encontrados pela API Discord: "+", ".join(missing))
   print("VERIFICAÇÃO OK")
  finally:
   await self.close()
if not TOKEN:raise SystemExit("Segredo DISCORD_BOT_TOKEN ausente.")
Verify().run(TOKEN)
