"""Render the Irmandade welcome card with an animated background."""

import asyncio
import hashlib
import logging
import re
import time
from io import BytesIO
from pathlib import Path

import discord
from aiohttp import ClientError, ClientSession, ClientTimeout
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

BACKGROUND_URL = "https://alan-alves.com/assets/alunos-dev-club-boas-vindas.gif"
SIZE = (480, 270)
BACKGROUND_LIMIT = 8 * 1024 * 1024
CARD_LIMIT = 5 * 1024 * 1024
WELCOME_CHANNEL_NAME = re.compile(r"(?<!\w)boas[-_ ]vindas(?!\w)", re.I)
BACKGROUND_TTL = 3600
background_lock = asyncio.Lock()
render_slot = asyncio.Semaphore(1)
background_cache: tuple[bytes, float] | None = None


def welcome_channel(guild):
    if guild is None or guild.me is None:
        return None
    matches = [
        ch for ch in guild.text_channels
        if WELCOME_CHANNEL_NAME.search(ch.name) and ch.permissions_for(guild.default_role).view_channel
    ]
    if len(matches) != 1:
        return None
    channel = matches[0]
    permissions = channel.permissions_for(guild.me)
    if permissions.view_channel and permissions.send_messages and permissions.attach_files and permissions.embed_links:
        return channel
    return None


async def get_background():
    global background_cache
    async with background_lock:
        if background_cache and time.monotonic() - background_cache[1] < BACKGROUND_TTL:
            return background_cache[0]
        try:
            async with ClientSession(timeout=ClientTimeout(total=12)) as session:
                async with session.get(BACKGROUND_URL, allow_redirects=False) as response:
                    if response.status != 200:
                        raise ValueError("Não foi possível obter o GIF de fundo.")
                    data = bytearray()
                    async for part in response.content.iter_chunked(64 * 1024):
                        data.extend(part)
                        if len(data) > BACKGROUND_LIMIT:
                            raise ValueError("O GIF de fundo excede o limite.")
                    if not data.startswith((b"GIF87a", b"GIF89a")):
                        raise ValueError("O fundo recebido não está em formato GIF.")
            background_cache = (bytes(data), time.monotonic())
        except (ClientError, TimeoutError, ValueError):
            if background_cache is None:
                raise
            logging.warning("Usando a última cópia válida do fundo de boas-vindas.")
        return background_cache[0]


def welcome_font(size):
    path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default(size=size)


def card_overlay(avatar_bytes, display_name):
    width, height = SIZE
    center = width // 2
    with Image.open(BytesIO(avatar_bytes)) as avatar:
        avatar = ImageOps.fit(avatar.convert("RGBA"), (106, 106), Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", SIZE)
    draw = ImageDraw.Draw(overlay)
    for y in range(height):
        alpha = round(42 + 160 * (y / (height - 1)) ** 1.65)
        draw.line((0, y, width, y), fill=(4, 7, 17, alpha))
    draw.ellipse((center - 56, 26, center + 55, 137), fill="#ffd57d")
    mask = Image.new("L", avatar.size)
    ImageDraw.Draw(mask).ellipse((0, 0, 105, 105), fill=255)
    overlay.paste(avatar, (center - 53, 29), mask)

    def centered(text, baseline, size, fill):
        font = welcome_font(size)
        while size > 14 and draw.textlength(text, font=font) > width - 56:
            size -= 1
            font = welcome_font(size)
        while len(text) > 2 and draw.textlength(text, font=font) > width - 56:
            text = text.rstrip("…")[:-1] + "…"
        draw.text((center, baseline), text, font=font, anchor="mm", fill=fill,
                  stroke_width=2, stroke_fill="#0b0e18")

    centered("BOAS-VINDAS", 169, 39, "#ffd57d")
    centered(" ".join(display_name.split())[:80] or "Novo membro", 209, 26, "#ffffff")
    centered("À IRMANDADE", 241, 17, "#ffd57d")
    return overlay


def render_card(background_bytes, avatar_bytes, display_name):
    overlay = card_overlay(avatar_bytes, display_name)
    with Image.open(BytesIO(background_bytes)) as background:
        frame_count = background.n_frames
        if not 2 <= frame_count <= 300 or background.width * background.height > 2_100_000:
            raise ValueError("O fundo precisa ser um GIF animado de dimensões compatíveis.")

        for step in (max(1, (frame_count + 57) // 58), max(2, (frame_count + 31) // 32)):
            frames = []
            durations = []
            for index in range(frame_count):
                background.seek(index)
                duration = max(20, background.info.get("duration", 80))
                if index % step:
                    durations[-1] += duration
                    continue
                backdrop = ImageOps.fit(background.convert("RGBA"), SIZE, Image.Resampling.LANCZOS)
                backdrop.alpha_composite(overlay)
                frames.append(backdrop.convert("RGB").quantize(colors=128))
                durations.append(duration)
            output = BytesIO()
            frames[0].save(output, format="GIF", save_all=True, append_images=frames[1:],
                           duration=durations, loop=0, disposal=1, optimize=True)
            if output.tell() <= CARD_LIMIT:
                return output.getvalue()
    raise ValueError("O cartão animado excede o limite de envio.")


async def generate_member_card(member):
    async with render_slot:
        background, avatar = await asyncio.gather(
            get_background(),
            asyncio.wait_for(member.display_avatar.with_size(256).with_format("png").read(), timeout=10),
        )
        return await asyncio.to_thread(render_card, background, avatar, member.display_name)


async def send_member_welcome(member):
    if member.bot:
        return
    channel = welcome_channel(member.guild)
    if channel is None:
        logging.warning("Boas-vindas não enviadas: canal indisponível ou sem permissão.")
        return
    try:
        gif = await generate_member_card(member)
        nonce = hashlib.sha256(f"{member.guild.id}:{member.id}:{member.joined_at}".encode()).hexdigest()[:25]
        embed = discord.Embed(
            title="Boas-vindas à Irmandade! 👋",
            description="Apresente-se, compartilhe seus projetos e venha aprender com a comunidade.",
            color=0xFFD57D,
        )
        filename = "boas-vindas-irmandade.gif"
        embed.set_image(url=f"attachment://{filename}")
        with BytesIO(gif) as buffer:
            await channel.send(
                f"Que bom ter você aqui, {member.mention}!",
                embed=embed,
                file=discord.File(buffer, filename=filename),
                allowed_mentions=discord.AllowedMentions(everyone=False, users=[member], roles=False),
                nonce=nonce,
            )
        logging.info("Boas-vindas automática enviada no canal %s.", channel.id)
    except (discord.DiscordException, ClientError, TimeoutError, ValueError, UnidentifiedImageError, OSError):
        logging.exception("Falha ao gerar ou publicar as boas-vindas automáticas.")
