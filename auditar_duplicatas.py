"""Auditoria segura de duplicatas no ALUNOS DEV-CLUB. Não exclui canais."""
import os, asyncio, unicodedata, re
from collections import defaultdict
import discord

GUILD_ID=1246627128074567680
TOKEN=os.environ.get("DISCORD_BOT_TOKEN")
def normalized(name):
    name=unicodedata.normalize("NFKC",name).casefold()
    name=re.sub(r"[^\w\s-]"," ",name)
    return re.sub(r"\s+","-",name).strip("-")

class Audit(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents(guilds=True))
        self.failed=False
    async def on_ready(self):
        try:
            guild=self.get_guild(GUILD_ID)
            if not guild: raise RuntimeError("Bot não encontrou o servidor.")
            channels=await guild.fetch_channels()
            grouped=defaultdict(list)
            for ch in channels:
                if isinstance(ch,(discord.TextChannel,discord.VoiceChannel)):
                    grouped[(ch.category_id,normalized(ch.name),type(ch).__name__)].append(ch)
            count=0
            for (category_id,key,kind),matches in sorted(grouped.items(),key=lambda x:str(x[0])):
                if len(matches)<2: continue
                count+=1
                print(f"\nDUPLICATA {count} | categoria={category_id} | tipo={kind} | nome_normalizado={key}",flush=True)
                for ch in matches:
                    details=f"ID={ch.id} | nome={ch.name} | criado={ch.created_at.isoformat()}"
                    if isinstance(ch,discord.TextChannel):
                        try:
                            messages=[m async for m in ch.history(limit=1)]
                            details+=f" | possui_mensagens={bool(messages)}"
                        except discord.Forbidden:
                            details+=" | histórico=SEM PERMISSÃO (PRESERVAR)"
                        except Exception as ex:
                            details+=f" | histórico=ERRO {type(ex).__name__} (PRESERVAR)"
                    print(details,flush=True)
            print(f"\nRESUMO: {len(channels)} canais; {count} grupos duplicados exatos na mesma categoria.",flush=True)
            print("MODO SOMENTE LEITURA: nenhum canal foi excluído ou alterado.",flush=True)
        except Exception as ex:
            self.failed=True
            print("FALHA:",repr(ex),flush=True)
        finally:
            await self.close()
if not TOKEN: raise SystemExit("Segredo DISCORD_BOT_TOKEN não configurado.")
client=Audit()
client.run(TOKEN)
if client.failed: raise SystemExit("Auditoria falhou.")
