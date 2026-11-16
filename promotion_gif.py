"""Convert uploaded videos into looping GIF attachments for Discord."""

import asyncio
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from imageio_ffmpeg import get_ffmpeg_exe

MAX_VIDEO_SECONDS = 60
MAX_GIF_BYTES = 20 * 1024 * 1024
VIDEO_LIMIT_MESSAGE = "Escolha um vídeo de até 60 segundos para gerar o GIF completo."
DURATION = re.compile(rb"Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)")
OUTPUT_TIME = re.compile(rb"^out_time_us=(\d+)$", re.M)
conversion_slot = asyncio.Semaphore(1)


class GifConversionError(ValueError):
    pass


async def run_ffmpeg(*args, loglevel="error"):
    process = await asyncio.create_subprocess_exec(
        get_ffmpeg_exe(), "-hide_banner", "-nostdin", "-loglevel", loglevel,
        "-max_alloc", str(64 * 1024 * 1024), "-filter_threads", "1",
        "-filter_complex_threads", "1", "-y", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await process.communicate()
    finally:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
    if process.returncode:
        raise GifConversionError("Não consegui ler o vídeo. Tente outro arquivo MP4, MOV ou WebM.")
    return stdout, stderr


async def encode_gif(raw, suffix, directory):
    source = directory / ("video" + suffix)
    palette = directory / "palette.png"
    target = directory / "promocao.gif"
    source.write_bytes(raw)

    input_args = [
        "-protocol_whitelist", "file,pipe", "-threads", "1",
        "-max_pixels", str(16 * 1024 * 1024),
        "-f", "matroska" if suffix == ".webm" else "mov",
        *([] if suffix == ".webm" else ["-enable_drefs", "0"]),
        "-i", str(source),
    ]
    _, metadata = await run_ffmpeg(
        *input_args, "-map", "0:v:0", "-an", "-t", "0", "-f", "null", "-",
        loglevel="info",
    )
    duration = DURATION.search(metadata)
    if duration:
        hours, minutes, seconds = map(float, duration.groups())
        if hours * 3600 + minutes * 60 + seconds > MAX_VIDEO_SECONDS + 0.05:
            raise GifConversionError(VIDEO_LIMIT_MESSAGE)

    for edge, fps in ((480, 12), (360, 10), (280, 8)):
        resize = (
            f"fps={fps},scale=w='min(iw,{edge})':h='min(ih,{edge})':"
            "force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos"
        )
        max_seconds = str(MAX_VIDEO_SECONDS + 1)
        await run_ffmpeg(
            *input_args, "-t", max_seconds, "-map", "0:v:0",
            "-vf", f"trim=duration={max_seconds},{resize},palettegen",
            "-frames:v", "1", "-update", "1", "-threads", "1", str(palette),
        )
        progress, _ = await run_ffmpeg(
            *input_args, "-i", str(palette), "-an",
            "-filter_complex", f"[0:v]trim=duration={max_seconds},{resize}[clip];[clip][1:v]paletteuse=dither=bayer:bayer_scale=3[gif]",
            "-map", "[gif]", "-t", max_seconds, "-loop", "0", "-threads", "1",
            "-fs", str(MAX_GIF_BYTES + 1), "-progress", "pipe:1", str(target),
        )
        times = OUTPUT_TIME.findall(progress)
        if times and int(times[-1]) > (MAX_VIDEO_SECONDS + 0.5) * 1_000_000:
            raise GifConversionError(VIDEO_LIMIT_MESSAGE)
        size = target.stat().st_size
        if 0 < size <= MAX_GIF_BYTES:
            result = target.read_bytes()
            if result.startswith((b"GIF87a", b"GIF89a")) and result.endswith(b";"):
                return result
            raise GifConversionError("Não foi possível produzir um GIF válido com esse vídeo.")
        if size == 0:
            raise GifConversionError("O vídeo selecionado não tem quadros suficientes para gerar o GIF.")

    raise GifConversionError("O GIF ficou maior que 20 MiB. Escolha um vídeo mais curto.")


async def video_to_gif(raw, filename):
    suffix = Path(filename).suffix
    try:
        async with asyncio.timeout(80):
            async with conversion_slot:
                with TemporaryDirectory(prefix="alan-discord-gif-") as scratch:
                    return await encode_gif(raw, suffix, Path(scratch))
    except TimeoutError as error:
        raise GifConversionError("A conversão demorou demais. Escolha um vídeo mais curto e tente novamente.") from error
