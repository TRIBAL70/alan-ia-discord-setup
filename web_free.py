"""Render free web service for Alan IA. Free instances may sleep on inactivity."""
import asyncio
import logging
import os
from aiohttp import web
from bot import client, TOKEN

logging.basicConfig(level=logging.INFO)
async def health(request):
    return web.json_response({
        "service": "alan-ia",
        "discord_connected": bool(client.user and not client.is_closed()),
        "configured": bool(TOKEN),
        "notice": "Instâncias gratuitas podem suspender por inatividade."
    })

async def startup(app):
    if TOKEN:
        app["bot_task"] = asyncio.create_task(client.start(TOKEN))
        app["bot_task"].add_done_callback(
            lambda task: logging.error("Bot terminou: %s",task.exception()) if not task.cancelled() and task.exception() else None
        )
    else:
        logging.warning("DISCORD_BOT_TOKEN não configurado: serviço web funciona, bot permanece offline.")

async def cleanup(app):
    if "bot_task" in app:
        await client.close()
        app["bot_task"].cancel()
        try:
            await app["bot_task"]
        except asyncio.CancelledError:
            pass

app=web.Application()
app.router.add_get("/",health)
app.router.add_get("/health",health)
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)

if __name__=="__main__":
    web.run_app(app,host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
