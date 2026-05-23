"""Interactive Telethon authentication helper.

Use this if the default flow in ``import_history.py`` fails to deliver
the login code. This script offers a more verbose authentication flow
with an option to switch to SMS delivery if the Telegram-app code
doesn't arrive.

Once authenticated, ``telethon.session`` is written to the project
root. ``import_history.py`` will reuse it and no longer ask for
credentials.

Usage:
    python scripts/telethon_auth.py
"""

from __future__ import annotations

import asyncio
import getpass
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from telethon import TelegramClient  # noqa: E402
from telethon.errors import (  # noqa: E402
    FloodWaitError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from config import TELEGRAM_API_HASH, TELEGRAM_API_ID  # noqa: E402

SESSION_PATH = PROJECT_ROOT / "telethon"


async def main() -> None:
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        print("❌ TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        sys.exit(1)

    client = TelegramClient(
        str(SESSION_PATH), TELEGRAM_API_ID, TELEGRAM_API_HASH
    )
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        uname = f"@{me.username}" if me.username else f"id={me.id}"
        print(f"✓ Already logged in as {me.first_name} ({uname})")
        await client.disconnect()
        return

    print("=" * 60)
    print("Telethon authentication helper")
    print("=" * 60)
    print()

    while True:
        phone = input(
            "📱 Phone (with + and country code, e.g. +380...): "
        ).strip()
        if not phone.startswith("+") or len(phone) < 8:
            print("   ❌ Invalid format. Example: +380677219288")
            continue
        break

    print()
    print(f"📤 Requesting login code for {phone} via Telegram app...")

    try:
        sent = await client.send_code_request(phone, force_sms=False)
    except FloodWaitError as exc:
        print(f"❌ Telegram is rate-limited. Wait {exc.seconds}s and retry.")
        await client.disconnect()
        return
    except PhoneNumberInvalidError:
        print("❌ Phone number invalid — check it's a real Telegram account.")
        await client.disconnect()
        return
    except Exception as exc:
        print(f"❌ Failed to request code: {exc}")
        await client.disconnect()
        return

    code_type = type(sent.type).__name__.replace("SentCodeType", "")
    print(f"✓ Code requested. Telegram says delivery type: {code_type}")
    print()
    print("   📲 Open Telegram app → look for chat with 'Telegram' "
          "(service account) and find the code there.")
    print("   📱 If nothing arrives in 1–2 min, type 'sms' below to "
          "resend via SMS.")
    print()

    code_hash = sent.phone_code_hash

    while True:
        code = input(
            "Code (or 'sms' to resend via SMS, 'q' to cancel): "
        ).strip()

        if not code:
            continue

        if code.lower() == "q":
            print("Cancelled.")
            await client.disconnect()
            sys.exit(0)

        if code.lower() == "sms":
            try:
                print("📤 Resending via SMS...")
                sent = await client.send_code_request(phone, force_sms=True)
                code_hash = sent.phone_code_hash
                kind = type(sent.type).__name__.replace("SentCodeType", "")
                print(f"   ✓ Sent ({kind}). Check SMS on {phone}.")
                print()
                continue
            except FloodWaitError as exc:
                print(f"   ❌ Wait {exc.seconds}s before SMS retry.")
                continue
            except Exception as exc:
                print(f"   ❌ SMS resend failed: {exc}")
                continue

        try:
            await client.sign_in(
                phone=phone, code=code, phone_code_hash=code_hash
            )
            break
        except PhoneCodeInvalidError:
            print("   ❌ Wrong code. Try again.")
            continue
        except SessionPasswordNeededError:
            print()
            pw = getpass.getpass(
                "🔐 2FA password (characters are hidden as you type): "
            ).strip()
            try:
                await client.sign_in(password=pw)
                break
            except Exception as exc:
                print(f"   ❌ 2FA failed: {exc}")
                continue
        except Exception as exc:
            print(f"   ❌ Sign-in error: {exc}")
            continue

    me = await client.get_me()
    uname = f"@{me.username}" if me.username else f"id={me.id}"

    print()
    print("=" * 60)
    print(f"✓ Logged in as: {me.first_name} ({uname})")
    print(f"✓ Session saved.")
    print()
    print("Next step: run `python scripts/import_history.py --hide-seed`")
    print("=" * 60)

    await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
