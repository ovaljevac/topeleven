"""Sigurna Discord kontrola za Top Eleven agente."""

from __future__ import annotations

import asyncio
import json
import msvcrt
import os
import subprocess
import sys
from dataclasses import dataclass, field
from agent_artifacts import read_failure_events, failure_caption
from datetime import datetime
from pathlib import Path

try:
    import discord
    from discord import app_commands
except ImportError:
    print("Nedostaje discord.py. Pokreni: python -m pip install -r requirements.txt")
    raise SystemExit(1)


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "discord_config.json"
LOG_ROOT = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "TopElevenAgent" / "logs"
BOT_LOCK_PATH = Path(os.environ.get("LOCALAPPDATA", ROOT)) / "TopElevenAgent" / "discord-bot.lock"
POWERSHELL_EXE = (
    Path(os.environ.get("WINDIR", r"C:\Windows"))
    / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
)

SCRIPTS = {
    "sve": ("Sve", "Pokreni sve faze"),
    "zeleni": ("Zeleni", "Uzmi 25 zelenih"),
    "odmor": ("OdmoriEkipu", "Odmori ekipu od GK"),
    "tv": ("TV", "Top Eleven TV"),
    "mourinho": ("Mourinho", "Mourinho nagrada"),
    "kampus": ("Kampus", "Kampus objekti"),
    "savez": ("PutSaveza", "Put saveza"),
    "trening": ("TreningIgraca", "Trening igraca"),
    "start": ("Start", "Pokreni Top Eleven"),
    "restart": ("Restart", "Restartuj Top Eleven"),
}


@dataclass
class RunningAgent:
    key: str
    process: asyncio.subprocess.Process
    log_path: Path
    stop_path: Path
    stderr_path: Path
    channel: discord.abc.Messageable
    started_at: datetime
    announced_lines: int = 0
    announced_errors: set[str] = field(default_factory=set)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            "Nedostaje discord_config.json. Kopiraj discord_config.example.json, "
            "preimenuj ga i upisi token/ID brojeve."
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not config.get("token") or str(config["token"]).startswith("OVDJE_"):
        raise RuntimeError("Upisi pravi bot token u discord_config.json.")
    if not config.get("allowed_user_ids"):
        raise RuntimeError("allowed_user_ids ne smije biti prazan.")
    return config


def acquire_single_instance_lock():
    """Keep exactly one Discord gateway client active for this Windows user."""
    BOT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = BOT_LOCK_PATH.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        raise RuntimeError("Discord bot vec radi. Ne pokreci drugu kopiju.")
    return handle


def powershell_command(mode: str, log_path: Path, stop_path: Path, resume: bool = False) -> list[str]:
    return [
        str(POWERSHELL_EXE), "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass",
        "-File", str(ROOT / "TopElevenAgent.ps1"),
        "-Mode", mode,
        "-AutoStart",
        "-ExitAfterRun",
        "-LogPath", str(log_path),
        "-StopSignalPath", str(stop_path),
    ] + (["-Resume"] if resume else [])


def discord_chunks(text: str, limit: int = 1800) -> list[str]:
    lines = text.splitlines() or [text]
    chunks: list[str] = []
    current = ""
    for line in lines:
        line = line[-limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


class TopElevenBot(discord.Client):
    def __init__(self, config: dict):
        super().__init__(intents=discord.Intents.none())
        self.tree = app_commands.CommandTree(self)
        self.config = config
        self.running: RunningAgent | None = None
        self.monitor_task: asyncio.Task | None = None
        self.start_lock = asyncio.Lock()

    async def setup_hook(self) -> None:
        guild_id = self.config.get("guild_id")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    def allowed(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id in {int(x) for x in self.config["allowed_user_ids"]}

    async def reject_if_needed(self, interaction: discord.Interaction) -> bool:
        if self.allowed(interaction):
            return False
        await interaction.response.send_message("Nemas dozvolu za kontrolu agenta.", ephemeral=True)
        return True

    async def monitor(self, run: RunningAgent) -> None:
        try:
            while run.process.returncode is None:
                await asyncio.sleep(4)
                try:
                    await self.send_new_log(run)
                    await self.send_failure_evidence(run)
                except Exception as exc:
                    # A network/log failure does not mean the child exited.
                    # Keep its handle so /status and /stop remain usable.
                    print(f"Privremena greska pracenja: {exc}", flush=True)
            await self.send_new_log(run)
            await self.send_failure_evidence(run)
            code = await run.process.wait()
            label = SCRIPTS[run.key][1]
            if run.stop_path.exists():
                result = f"⏹️ **{label}** je zaustavljen."
            elif code == 0:
                result = f"✅ **{label}** je zavrsio rad."
            else:
                windows_code = code & 0xFFFFFFFF
                result = f"❌ **{label}** je zavrsio s kodom greske `{windows_code}` (`0x{windows_code:08X}`)."
                if run.stderr_path.exists():
                    detail = run.stderr_path.read_text(encoding="utf-8", errors="replace").strip()
                    if detail:
                        result += f"\n```text\n{detail[-1200:]}\n```"
            await run.channel.send(result)
        except Exception as exc:
            try:
                await run.channel.send(f"⚠️ Greska pri pracenju loga: `{exc}`")
            except Exception:
                pass
        finally:
            if self.running is run and run.process.returncode is not None:
                self.running = None

    async def send_failure_evidence(self, run: RunningAgent) -> None:
        for event_id, event, image in read_failure_events(run.log_path, run.announced_errors):
            try:
                kwargs = {"allowed_mentions": discord.AllowedMentions.none()}
                if image is not None:
                    attachment = discord.File(str(image), filename="bluestacks-error.png")
                    try:
                        await run.channel.send(failure_caption(event), file=attachment, **kwargs)
                    finally:
                        attachment.close()
                else:
                    await run.channel.send(failure_caption(event), **kwargs)
                run.announced_errors.add(event_id)
            except (discord.HTTPException, OSError):
                # Attachment failures must not stop process monitoring or hide the error.
                try:
                    await run.channel.send(failure_caption(event) + '\nSlanje slike nije uspjelo; sacuvana je lokalno.', allowed_mentions=discord.AllowedMentions.none())
                    run.announced_errors.add(event_id)
                except discord.HTTPException:
                    pass

    async def send_new_log(self, run: RunningAgent) -> None:
        if not self.config.get("live_log", True) or not run.log_path.exists():
            return
        try:
            lines = run.log_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        except OSError:
            return
        new_lines = lines[run.announced_lines:]
        if not new_lines:
            return
        # Grupisanje sprjecava jednu Discord poruku za svaki red loga.
        for chunk in discord_chunks("\n".join(new_lines)):
            await run.channel.send(f"```text\n{chunk}\n```", allowed_mentions=discord.AllowedMentions.none())
        run.announced_lines = len(lines)


try:
    single_instance_lock = acquire_single_instance_lock()
except RuntimeError as exc:
    print(exc)
    raise SystemExit(2)

config = load_config()
bot = TopElevenBot(config)


SCRIPT_CHOICES = [app_commands.Choice(name=description, value=key) for key, (_, description) in SCRIPTS.items()]


@bot.tree.command(name="skripte", description="Prikazi skripte koje bot smije pokrenuti")
async def scripts(interaction: discord.Interaction) -> None:
    if await bot.reject_if_needed(interaction):
        return
    text = "\n".join(f"`{key}` — {description}" for key, (_, description) in SCRIPTS.items())
    await interaction.response.send_message(f"**Dostupne skripte**\n{text}", ephemeral=True)


@bot.tree.command(name="pokreni", description="Pokreni jednu dozvoljenu Top Eleven skriptu")
@app_commands.choices(skripta=SCRIPT_CHOICES)
async def start(interaction: discord.Interaction, skripta: app_commands.Choice[str]) -> None:
    await start_script(interaction, skripta.value)


async def start_script(interaction: discord.Interaction, key: str, resume: bool = False) -> None:
    # Reserve the launch across create_subprocess_exec's await: two commands
    # arriving together must not overwrite the process tracked by /stop.
    async with bot.start_lock:
        await _start_script_locked(interaction, key, resume)


async def _start_script_locked(interaction: discord.Interaction, key: str, resume: bool = False) -> None:
    if await bot.reject_if_needed(interaction):
        return
    if bot.running and bot.running.process.returncode is None:
        await interaction.response.send_message(
            f"Vec radi **{SCRIPTS[bot.running.key][1]}**. Prvo koristi `/zaustavi`.", ephemeral=True
        )
        return
    mode, label = SCRIPTS[key]
    await interaction.response.defer()
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    log_path = LOG_ROOT / f"discord-{run_id}-{mode}.log"
    stop_path = LOG_ROOT / f"discord-{run_id}.stop"
    stderr_path = LOG_ROOT / f"discord-{run_id}-{mode}.stderr.log"
    log_path.write_text("", encoding="utf-8")
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        with stderr_path.open("wb") as stderr_file:
            process = await asyncio.create_subprocess_exec(
                *powershell_command(mode, log_path, stop_path, resume=resume),
                cwd=str(ROOT), creationflags=creationflags, stderr=stderr_file,
            )
    except OSError as exc:
        await interaction.followup.send(f"Pokretanje nije uspjelo: `{exc}`", ephemeral=True)
        return
    run = RunningAgent(key, process, log_path, stop_path, stderr_path, interaction.channel, datetime.now())
    bot.running = run
    bot.monitor_task = asyncio.create_task(bot.monitor(run))
    await interaction.followup.send(f"▶️ Pokrenut je **{label}** (PID `{process.pid}`).")


@bot.tree.command(name="nastavi", description="Nastavi danasnji sacuvani napredak nakon provjere ekrana")
@app_commands.choices(skripta=[choice for choice in SCRIPT_CHOICES if choice.value not in {"start", "restart"}])
async def resume_script(interaction: discord.Interaction, skripta: app_commands.Choice[str]) -> None:
    await start_script(interaction, skripta.value, resume=True)


@bot.tree.command(name="sve", description="Odmah pokreni sve Top Eleven faze")
async def start_all(interaction: discord.Interaction) -> None:
    await start_script(interaction, "sve")


@bot.tree.command(name="zeleni", description="Odmah pokreni uzimanje 25 zelenih")
async def start_greens(interaction: discord.Interaction) -> None:
    await start_script(interaction, "zeleni")


@bot.tree.command(name="odmor", description="Odmah pokreni odmor ekipe")
async def start_rest(interaction: discord.Interaction) -> None:
    await start_script(interaction, "odmor")


@bot.tree.command(name="tv", description="Odmah pokreni Top Eleven TV")
async def start_tv(interaction: discord.Interaction) -> None:
    await start_script(interaction, "tv")


@bot.tree.command(name="mourinho", description="Odmah pokreni Mourinho nagradu")
async def start_mourinho(interaction: discord.Interaction) -> None:
    await start_script(interaction, "mourinho")


@bot.tree.command(name="kampus", description="Odmah pokreni Kampus")
async def start_campus(interaction: discord.Interaction) -> None:
    await start_script(interaction, "kampus")


@bot.tree.command(name="savez", description="Odmah pokreni Put saveza")
async def start_alliance(interaction: discord.Interaction) -> None:
    await start_script(interaction, "savez")


@bot.tree.command(name="trening", description="Odmah pokreni trening igraca")
async def start_training(interaction: discord.Interaction) -> None:
    await start_script(interaction, "trening")


@bot.tree.command(name="restart", description="Potpuno ugasi i ponovo pokreni Top Eleven")
async def restart_top_eleven(interaction: discord.Interaction) -> None:
    await start_script(interaction, "restart")


@bot.tree.command(name="start", description="Pokreni Top Eleven samo ako je zatvoren")
async def start_top_eleven(interaction: discord.Interaction) -> None:
    await start_script(interaction, "start")


@bot.tree.command(name="status", description="Provjeri sta agent trenutno radi")
async def status(interaction: discord.Interaction) -> None:
    if await bot.reject_if_needed(interaction):
        return
    run = bot.running
    if not run or run.process.returncode is not None:
        await interaction.response.send_message("Trenutno nijedna skripta ne radi.", ephemeral=True)
        return
    duration = datetime.now() - run.started_at
    await interaction.response.send_message(
        f"🟢 Radi **{SCRIPTS[run.key][1]}** već `{str(duration).split('.')[0]}` (PID `{run.process.pid}`).",
        ephemeral=True,
    )


@bot.tree.command(name="log", description="Prikazi zadnje redove aktivnog loga")
async def log(interaction: discord.Interaction) -> None:
    if await bot.reject_if_needed(interaction):
        return
    run = bot.running
    if not run or not run.log_path.exists():
        await interaction.response.send_message("Nema aktivnog loga.", ephemeral=True)
        return
    lines = run.log_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[-20:]
    body = "\n".join(lines) or "Log je jos prazan."
    await interaction.response.send_message(f"```text\n{body[-1800:]}\n```", ephemeral=True)


@bot.tree.command(name="zaustavi", description="Sigurno zaustavi aktivnu skriptu")
async def stop(interaction: discord.Interaction) -> None:
    await stop_script(interaction)


async def stop_script(interaction: discord.Interaction) -> None:
    if await bot.reject_if_needed(interaction):
        return
    run = bot.running
    if not run or run.process.returncode is not None:
        await interaction.response.send_message("Trenutno nijedna skripta ne radi.", ephemeral=True)
        return
    run.stop_path.write_text("stop", encoding="utf-8")
    await interaction.response.send_message("⏳ Poslan je zahtjev za sigurno zaustavljanje.")


@bot.tree.command(name="stop", description="Sigurno zaustavi aktivnu skriptu")
async def stop_short(interaction: discord.Interaction) -> None:
    await stop_script(interaction)


@bot.event
async def on_ready() -> None:
    print(f"Discord bot je spreman kao {bot.user} (ID {bot.user.id}).", flush=True)


if __name__ == "__main__":
    try:
        bot.run(config["token"], log_handler=None)
    except discord.LoginFailure:
        print("Discord token nije ispravan.")
        sys.exit(1)
