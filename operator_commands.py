import asyncio
import io
from contextlib import closing

import discord

from error_reporting import (
    PUBLIC_ERROR_TEXT,
    IncidentStorageError,
    capture_incident,
    get_incident_store,
)
from response_observability import prepare_delivery

PRIVATE_ERROR_REPORT_MARKER = "\u2063\u2060\u2060\u2063"


def is_private_error_report(message, own_id) -> bool:
    return (
        own_id is not None
        and str(getattr(getattr(message, "author", None), "id", "")) == str(own_id)
        and PRIVATE_ERROR_REPORT_MARKER in str(getattr(message, "content", "") or "")
    )


def is_operator_command(message, prefix: str, own_id=None) -> bool:
    author = getattr(message, "author", None)
    content = str(getattr(message, "content", "") or "")
    parts = content[len(prefix):].strip().split(maxsplit=1) if content.startswith(prefix) else []
    return (
        bool(parts) and parts[0].lower() in {"error", "forward"}
        and not getattr(author, "bot", False)
        and str(getattr(author, "id", "")) != str(own_id)
    )


def ignore_operator_message(bot, message) -> bool:
    own_id = getattr(getattr(bot, "user", None), "id", None)
    return is_private_error_report(message, own_id) or is_operator_command(
        message, getattr(bot, "command_prefix", ","), own_id
    )


async def send_public_error(bot, channel) -> None:
    if bot._control.get("error_replies", True):
        await channel.send(PUBLIC_ERROR_TEXT, allowed_mentions=discord.AllowedMentions.none())


async def send_private_error_report(bot, author, text: str, *, report: bool) -> None:
    channel = await author.create_dm()
    if len(text) <= 1800:
        _, chunks = prepare_delivery(bot, text, None, unmeasured=False, code_block=report)
        for chunk in chunks:
            await channel.send(
                chunk + "\n" + PRIVATE_ERROR_REPORT_MARKER,
                allowed_mentions=discord.AllowedMentions.none(),
            )
    else:
        count = (len(text) + 999_999) // 1_000_000
        for index, offset in enumerate(range(0, len(text), 1_000_000), 1):
            part = text[offset:offset + 1_000_000]
            with io.BytesIO(part.encode("utf-8")) as buffer, closing(discord.File(
                buffer, filename=f"curie-error-{index}-of-{count}.txt"
            )) as attachment:
                await channel.send(
                    f"```\nPrivate error report — full details attached ({index}/{count}).\n```\n"
                    + PRIVATE_ERROR_REPORT_MARKER,
                    file=attachment,
                    allowed_mentions=discord.AllowedMentions.none(),
                )


async def handle_error_command(bot, message, args: str | None) -> None:
    if not bot._is_admin(message.author.id):
        await message.channel.send("not authorized", allowed_mentions=discord.AllowedMentions.none())
        return
    argument = (args or "").strip()
    report = False
    if not argument:
        text = (
            f"You need to use {bot.command_prefix}error 0 to 9 to recover the last error; "
            "root made this call because is lazy and one extra number doesn't hurt as much "
            "as losing time and asking the agent again what was the syntax he made up in a rush"
        )
    elif argument not in {str(index) for index in range(10)}:
        text = f"Only the last 10 errors are kept. Use {bot.command_prefix}error 0–9: 0 is newest, 9 is oldest."
    else:
        store = get_incident_store()
        try:
            incident = await asyncio.to_thread(store.get, int(argument)) if store is not None else None
            text = incident.format_report() if incident is not None else f"No saved error at index {argument}."
            report = incident is not None
        except IncidentStorageError as exc:
            text = f"Incident history is unavailable:\n{exc}"
            report = True
    try:
        await send_private_error_report(bot, message.author, text, report=report)
    except Exception as exc:
        capture_incident(
            "discord.error-report", "Could not deliver private error report", exception=exc,
            context={"user": str(message.author.id), "channel": str(message.channel.id), "requested_index": argument},
        )
        try:
            await send_public_error(bot, message.channel)
        except Exception as notice_error:
            capture_incident("discord.error-report", "Could not deliver generic failure notice", exception=notice_error)


async def handle_forward_command(bot, message, args: str | None) -> None:
    if not bot._is_admin(message.author.id):
        await message.channel.send("not authorized", allowed_mentions=discord.AllowedMentions.none())
        return
    argument = (args or "").strip()
    if not argument.isascii() or not argument.isdecimal() or int(argument) < 1:
        await message.channel.send(
            f"Usage: {bot.command_prefix}forward <positive number of my messages>",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return
    count = int(argument)
    lock = bot._forward_locks.setdefault(str(message.channel.id), asyncio.Lock())
    async with lock:
        selected, completed, absent = [], [], []
        phase, target = "history", ""
        try:
            async for candidate in message.channel.history(limit=None, before=message):
                if (candidate.author.id == bot.user.id and candidate.id < message.id
                        and candidate.channel.id == message.channel.id):
                    selected.append(candidate)
                    if len(selected) == count:
                        break
            phase = "delete"
            for candidate in selected:
                target = str(candidate.id)
                bot._forward_delete_ids.add(candidate.id)
                try:
                    await candidate.delete()
                except discord.NotFound:
                    absent.append(candidate.id)
                else:
                    completed.append(candidate.id)
        except Exception as exc:
            capture_incident(
                "discord.forward", "Forward command failed", exception=exc,
                details=(
                    f"requested_count: {count}\nphase: {phase}\nfailed_target: {target or '-'}\n"
                    f"selected_ids: {[item.id for item in selected]}\n"
                    f"completed_ids: {completed}\nabsent_ids: {absent}"
                ),
                context={
                    "channel": str(message.channel.id), "message": str(message.id),
                    "user": str(message.author.id),
                    "guild": str(getattr(getattr(message, "guild", None), "id", "DM")),
                },
            )
            raise
