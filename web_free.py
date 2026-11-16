"""Render free web service for Alan IA. Free instances may sleep on inactivity.
Redeploy to apply Render environment-group configuration.
"""
import asyncio
import base64
import binascii
import hashlib
import logging
import os
import re
from io import BytesIO
from urllib.parse import urlsplit
from uuid import UUID

import discord
from aiohttp import ClientError, ClientSession, ClientTimeout, web
from bot import GUILD_ID, TOKEN, _IMAGE_SUFFIXES, _RICH_MESSAGE_COLORS, client
from welcome_cards import generate_member_card, welcome_channel
from promotion_gif import GifConversionError, video_to_gif

logging.basicConfig(level=logging.INFO)
async def health(request):
    return web.json_response({
        "service": "alan-ia",
        "discord_connected": bool(client.user and not client.is_closed()),
        "configured": bool(TOKEN),
        "welcome_events": client.intents.members,
        "welcome_channel_ready": welcome_channel(client.get_guild(GUILD_ID)) is not None,
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


CRM_SUPABASE_URL = "https://kylriieztbcogpnsxgms.supabase.co"
CRM_PUBLIC_KEY = os.environ.get("CRM_SUPABASE_PUBLISHABLE_KEY", "")
HTTP_SESSION = web.AppKey("crm_http", ClientSession)
MAX_IMAGE = 5 * 1024 * 1024
MAX_VIDEO = 20 * 1024 * 1024
MAX_ATTACHMENT_BASE64 = 4 * ((MAX_VIDEO + 2) // 3)
VIDEO_SUFFIXES = {"video/mp4": "mp4", "video/quicktime": "mov", "video/webm": "webm"}
ID_PATTERN = re.compile(r"[0-9]{17,20}")


def crm_error(message, status):
    return web.json_response({"error": message}, status=status)


async def crm_admin(request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer ") or authorization.count(".") != 2:
        return crm_error("Entre no CRM novamente.", 401)
    if not CRM_PUBLIC_KEY:
        return crm_error("A integração com o CRM está indisponível.", 503)

    headers = {"apikey": CRM_PUBLIC_KEY, "Authorization": authorization}
    session = request.app[HTTP_SESSION]
    try:
        async with session.get(
            f"{CRM_SUPABASE_URL}/auth/v1/user", headers=headers, allow_redirects=False
        ) as response:
            if response.status in (401, 403):
                return crm_error("Sua sessão expirou. Entre no CRM novamente.", 401)
            response.raise_for_status()
            user_id = str(UUID((await response.json())["id"]))

        filters = {"select": "role", "user_id": f"eq.{user_id}", "role": "eq.admin", "limit": "1"}
        async with session.get(
            f"{CRM_SUPABASE_URL}/rest/v1/user_roles",
            headers=headers,
            params=filters,
            allow_redirects=False,
        ) as response:
            if response.status in (401, 403):
                return crm_error("Esta operação exige acesso de administrador.", 403)
            response.raise_for_status()
            roles = await response.json()
    except (ClientError, TimeoutError, ValueError, KeyError, TypeError):
        logging.warning("Falha ao verificar autorização do CRM.")
        return crm_error("Não foi possível verificar seu acesso ao CRM.", 503)

    if roles != [{"role": "admin"}]:
        return crm_error("Esta operação exige acesso de administrador.", 403)
    return user_id


def can_publish(channel, bot_member, *, attachment=False):
    permissions = channel.permissions_for(bot_member)
    return (
        channel.permissions_for(channel.guild.default_role).view_channel
        and permissions.view_channel
        and permissions.send_messages
        and permissions.embed_links
        and (not attachment or permissions.attach_files)
    )


CRM_BROWSER_ORIGINS = {
    "https://alan-alves-crm-comando.lovable.app",
    "https://id-preview--b55516d9-31ce-45d9-9b08-5607ab6c7484.lovable.app",
}
CRM_BROWSER_METHODS = {
    "/crm/discord/channels": "GET",
    "/crm/discord/promotions": "POST",
    "/crm/discord/welcome-member": "POST",
}


async def crm_response_headers(request, response):
    if request.path in CRM_BROWSER_METHODS:
        response.headers["Cache-Control"] = "no-store"
        response.headers.add("Vary", "Origin")
        origin = request.headers.get("Origin")
        if origin in CRM_BROWSER_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin


@web.middleware
async def crm_middleware(request, handler):
    method = CRM_BROWSER_METHODS.get(request.path)
    if method is None:
        return await handler(request)
    origin = request.headers.get("Origin")
    if origin is not None and origin not in CRM_BROWSER_ORIGINS:
        return crm_error("Origem não autorizada.", 403)
    if request.method == "OPTIONS":
        if origin is None or request.headers.get("Access-Control-Request-Method") != method:
            return crm_error("Método não autorizado.", 405)
        return web.Response(status=204, headers={
            "Access-Control-Allow-Methods": method,
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "600",
        })
    if request.method != method:
        return crm_error("Método não autorizado.", 405)
    admin = await crm_admin(request)
    if isinstance(admin, web.Response):
        return admin
    guild = client.get_guild(GUILD_ID)
    if not client.is_ready() or guild is None or guild.me is None:
        return crm_error("O Alan IA está se conectando ao Discord. Tente novamente.", 503)
    request["crm_admin"] = admin
    request["crm_guild"] = guild
    return await handler(request)


async def crm_welcome_member(request):
    try:
        payload = await request.json()
    except web.HTTPRequestEntityTooLarge:
        return crm_error("Identificador de membro inválido.", 413)
    except (ValueError, TypeError):
        return crm_error("Identificador de membro inválido.", 400)
    user_id = payload.get("user_id") if isinstance(payload, dict) else None
    if not isinstance(user_id, str) or not ID_PATTERN.fullmatch(user_id):
        return crm_error("Informe um ID de usuário do Discord.", 400)

    guild = request["crm_guild"]

    async def load_media():
        member = await guild.fetch_member(int(user_id))
        if payload.get("animated_card") is True:
            return {"card_gif": base64.b64encode(await generate_member_card(member)).decode("ascii")}
        avatar = await member.display_avatar.with_size(256).with_format("png").read()
        return {"display_name": member.display_name, "avatar_png": base64.b64encode(avatar).decode("ascii")}

    try:
        media = await asyncio.wait_for(load_media(), timeout=35)
    except discord.NotFound:
        return crm_error("Não encontrei esse membro no servidor.", 404)
    except (discord.DiscordException, ClientError, TimeoutError, ValueError, OSError):
        logging.warning("Não foi possível preparar a mídia de boas-vindas.", exc_info=True)
        return crm_error("Não foi possível gerar o cartão ou buscar o avatar. Tente novamente.", 502)

    return web.json_response(media)


async def crm_channels(request):
    guild = request["crm_guild"]
    channels = [
        {"id": str(ch.id), "name": ch.name, "category": ch.category.name if ch.category else None}
        for ch in guild.text_channels
        if can_publish(ch, guild.me)
    ]
    return web.json_response({"channels": channels})


def attachment_matches_mime(mime, raw):
    if mime in VIDEO_SUFFIXES:
        if mime == "video/webm":
            return raw.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in raw[:128]
        box = raw[4:8]
        size = int.from_bytes(raw[:4], "big") if len(raw) >= 8 else 0
        if len(raw) >= 12 and box == b"ftyp":
            return True
        return (
            mime == "video/quicktime"
            and (size == 1 or size >= 8)
            and box in (b"moov", b"mdat", b"wide", b"free")
        )
    signatures = {
        "image/gif": raw.startswith((b"GIF87a", b"GIF89a")),
        "image/jpeg": raw.startswith(b"\xff\xd8\xff"),
        "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP",
    }
    return signatures[mime]


def promotion_attachment(data):
    if not isinstance(data, dict):
        raise ValueError("Escolha uma imagem, GIF ou vídeo válido.")
    mime, encoded = data.get("mime"), data.get("data")
    if not isinstance(mime, str) or mime not in (_IMAGE_SUFFIXES | VIDEO_SUFFIXES):
        raise ValueError("Use PNG, JPG, WebP, GIF, MP4, MOV ou WebM.")
    is_video = mime in VIDEO_SUFFIXES
    limit = MAX_VIDEO if is_video else MAX_IMAGE
    limit_label = "20 MiB" if is_video else "5 MiB"
    if not isinstance(encoded, str) or len(encoded) > 4 * ((limit + 2) // 3):
        raise ValueError(f"O arquivo deve ter até {limit_label}.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("O arquivo enviado está inválido.") from exc
    if len(raw) > limit:
        raise ValueError(f"O arquivo deve ter até {limit_label}.")
    if not attachment_matches_mime(mime, raw):
        raise ValueError("O arquivo não corresponde ao formato indicado.")
    suffix = VIDEO_SUFFIXES[mime] if is_video else _IMAGE_SUFFIXES[mime]
    return raw, f"promocao.{suffix}", is_video

async def crm_publish(request):
    try:
        payload = await request.json()
    except web.HTTPRequestEntityTooLarge:
        return crm_error("O arquivo excede o limite de 20 MiB.", 413)
    except (ValueError, TypeError):
        return crm_error("Dados da promoção inválidos.", 400)
    if not isinstance(payload, dict):
        return crm_error("Dados da promoção inválidos.", 400)

    channel_id, request_id = payload.get("channel_id"), payload.get("request_id")
    title, text = payload.get("title"), payload.get("text")
    color, media_url = payload.get("color"), payload.get("media_url")
    source = payload.get("attachment")
    if (
        not isinstance(channel_id, str) or not ID_PATTERN.fullmatch(channel_id)
        or not isinstance(request_id, str) or len(request_id) != 36
        or not isinstance(title, str) or len(title) > 256
        or not isinstance(text, str) or len(text) > 4000
        or not isinstance(color, str) or color not in _RICH_MESSAGE_COLORS
    ):
        return crm_error("Confira o canal, a cor, o título e o texto da promoção.", 400)
    title, text = title.strip(), text.strip()
    if media_url is not None:
        try:
            parsed = urlsplit(media_url) if isinstance(media_url, str) else None
            valid = (
                parsed is not None and len(media_url) <= 2048 and parsed.scheme == "https"
                and parsed.hostname and parsed.username is None and parsed.password is None
                and not any(char.isspace() or ord(char) < 32 for char in media_url)
            )
        except ValueError:
            valid = False
        if not valid:
            return crm_error("Use um link HTTPS direto para a imagem ou GIF.", 400)
    if media_url and source is not None:
        return crm_error("Escolha um link ou um arquivo por promoção.", 400)
    if not (title or text or media_url or source is not None):
        return crm_error("Inclua um título, texto, imagem, GIF ou vídeo.", 400)
    guild = request["crm_guild"]
    channel = guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel) or not can_publish(
        channel, guild.me, attachment=source is not None
    ):
        return crm_error("O Alan IA não pode publicar nesse canal com as permissões atuais.", 403)

    try:
        attempt = UUID(request_id)
    except ValueError:
        return crm_error("Identificador de envio inválido.", 400)
    try:
        media_file = promotion_attachment(source) if source is not None else None
    except ValueError as error:
        return crm_error(str(error), 400)

    nonce = hashlib.sha256(
        f"{request['crm_admin']}:{channel_id}:{attempt}".encode()
    ).hexdigest()[:25]
    embed = discord.Embed(title=title or None, description=text or None, color=_RICH_MESSAGE_COLORS[color])
    args = {"embed": embed, "allowed_mentions": discord.AllowedMentions.none(), "nonce": nonce}
    if media_url:
        embed.set_image(url=media_url)
    if media_file:
        raw, filename, is_video = media_file
        if is_video:
            try:
                raw = await video_to_gif(raw, filename)
            except GifConversionError as error:
                return crm_error(str(error), 422)
            except OSError:
                logging.exception("Não foi possível iniciar a conversão em GIF.")
                return crm_error("O conversor de GIF está indisponível. Tente novamente.", 503)
            filename = "promocao.gif"
        args["file"] = discord.File(BytesIO(raw), filename=filename)
        embed.set_image(url=f"attachment://{filename}")

    timeout = 75 if media_file and media_file[2] else 20
    try:
        message = await asyncio.wait_for(channel.send(**args), timeout=timeout)
    except discord.Forbidden:
        return crm_error("O Alan Sky não tem permissão para publicar nesse canal.", 403)
    except discord.HTTPException as error:
        if error.status == 413 or error.code == 40005:
            return crm_error("O Discord recusou o tamanho do arquivo. Escolha um vídeo menor.", 413)
        return crm_error("Não foi possível confirmar o envio. Confira o canal antes de tentar novamente.", 502)
    except TimeoutError:
        return crm_error("Não foi possível confirmar o envio. Confira o canal antes de tentar novamente.", 502)
    finally:
        if "file" in args:
            args["file"].close()
    logging.info("Promoção publicada via CRM: canal=%s mensagem=%s", channel.id, message.id)
    return web.json_response({"message_url": message.jump_url})


async def crm_session(app):
    async with ClientSession(timeout=ClientTimeout(total=6)) as session:
        app[HTTP_SESSION] = session
        yield


app = web.Application(client_max_size=MAX_ATTACHMENT_BASE64 + 32_768, middlewares=[crm_middleware])
app.cleanup_ctx.append(crm_session)
app.on_response_prepare.append(crm_response_headers)
for path in CRM_BROWSER_METHODS:
    app.router.add_route("OPTIONS", path, crm_channels)
app.router.add_get('/crm/discord/channels', crm_channels)
app.router.add_post('/crm/discord/promotions', crm_publish)
app.router.add_post('/crm/discord/welcome-member', crm_welcome_member)
app.router.add_get("/",health)
app.router.add_get("/health",health)
app.on_startup.append(startup)
app.on_cleanup.append(cleanup)

if __name__=="__main__":
    web.run_app(app,host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
