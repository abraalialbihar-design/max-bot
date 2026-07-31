import os
import re
import io
import json
import math
import random
import asyncio
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
SOLD_WEBHOOK_URL = os.getenv("SOLD_WEBHOOK_URL", "")
# مسار التخزين الدائم: Railway يضبط RAILWAY_VOLUME_MOUNT_PATH تلقائياً فقط إذا قمت
# بربط Volume بالخدمة من لوحة تحكم Railway. بدون Volume، أي ملف محلي يُمسح بالكامل
# عند كل إعادة تشغيل/نشر لأن القرص نفسه مؤقت (ephemeral). راجع تعليمات الإعداد بالأسفل.
DATA_DIR = os.getenv("DATA_DIR") or os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or "."
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
SALES_COUNTER_FILE = os.path.join(DATA_DIR, "sales_counter.json")

# ==== الإعدادات الأساسية ====
DEFAULT_WELCOME_CHANNEL_ID = 1524371159020343318
DEFAULT_REVIEWS_CHANNEL_ID = 1525251733046038528
DEFAULT_TAX_CHANNEL_ID = 1525241937400037567
DEFAULT_BUY_CATEGORY_ID = 1531084521985015868

CUSTOMER_ROLE_ID = 1530380565130514583
BUY_ROLE_ID = 1530380477377024200

TICKET_NOTIFY_USER_ID = 1426552057984454817
TICKET_LOG_CHANNEL_ID = 1532468240985362682

STAR_EMOJI = "⭐"
EMBED_COLOR = discord.Color.from_rgb(47, 49, 54)
TICKET_EMBED_COLOR = discord.Color.blue()

DEFAULT_PAYMENT_METHODS = {
    "مدار": "لايوجد",
    "ليبيانا": "لايوجد",
    "بايننس": "لايوجد",
    "LTC": "لايوجد",
    "كريديت": "لايوجد"
}

AXION_TERMS = (
    "**1️⃣ -** يمنع طلب استبدال السلعة او استرداد الاموال بعد شرائك شي من المتجر ويجب أن تكون متأكدا قبل شرائك.\n\n"
    "**2️⃣ -** لا يحق للعميل طلب تخفيض سعر او شيء مجاني من المتجر.\n\n"
    "**3️⃣ -** يحق للعميل شراء هدية لشخص من منتجات المتجر.\n\n"
    "**4️⃣ -** جميع المشتريات تكون من خلال التذاكر المخصصة للمتجر فقط لا غير."
)

# =========================================================
# ============= أقسام التذاكر (لوحة الطلبات) =============
# =========================================================
TICKET_CATEGORIES = [
    {
        "key": "inquiry", "label": "استفسار على منتج",
        "emoji": "<:Support:1532171575653302397>", "prefix": "INQUIRY", "needs_username": False,
        "desc": "لو تبي تستفسر عن اي شيء يخص المتجر او يخص منتج يمكنك الضغط على زر إستفسار على منتج",
    },
    {
        "key": "fivem", "label": "Fivem",
        "emoji": "<:FIVEM:1530421877443530863>", "prefix": "FIVEM", "needs_username": False,
        "desc": "لو تبي تشتري حساب فايف ام او اي شيء ليه علاقة به اضغط علي",
    },
    {
        "key": "discord", "label": "Discord",
        "emoji": "<a:AT_Discord:1532164241270902854>", "prefix": "DISCORD", "needs_username": False,
        "desc": "لو تبي تشتري اي شيء يتعلق بالديسكورد من نيترو، بوستات، افكتات، او هايب سكواد اضغط علي",
    },
    {
        "key": "robux", "label": "Robux",
        "emoji": "<:Robux:1530419657209548841>", "prefix": "ROBUX", "needs_username": True,
        "desc": "لو تبي تشتري او تستفسر عن اي شيء يخص حساب او منتجات روبوكس اضغط علي",
    },
    {
        "key": "credit", "label": "Credit",
        "emoji": "<:Pro:1530379178635952200>", "prefix": "CREDIT", "needs_username": False,
        "desc": "لو تبي تشتري كريدت او رصيد اضغط علي",
    },
    {
        "key": "hosting", "label": "Hosting",
        "emoji": "<:OX_HOST:1532158984734375986>", "prefix": "HOST", "needs_username": False,
        "desc": "لو تبي تشتري استضافة او تستفسر عنها اضغط علي",
    },
    {
        "key": "snapchat", "label": "Snapchat",
        "emoji": "<:5378_snapchat:1532159134382686288>", "prefix": "SNAP", "needs_username": False,
        "desc": "لو تبي تشتري حساب سناب شات او اي شيء يخصه اضغط علي",
    },
    {
        "key": "dev", "label": "Dev",
        "emoji": "<:dev:1530379905148260542>", "prefix": "DEV", "needs_username": False,
        "desc": "لو تبي تطلب خدمة برمجة او بوت مخصص اضغط علي",
    },
    {
        "key": "windows", "label": "Windows",
        "emoji": "<:windows10100:1532163510753165443>", "prefix": "WINDOWS", "needs_username": False,
        "desc": "لو تبي تفعل نسخة ويندوز اضغط علي",
    },
    {
        "key": "visa", "label": "Visa",
        "emoji": "<:81603:1530379444584317091>", "prefix": "VISA", "needs_username": False,
        "desc": "لو تبي تشتري فيزا افتراضية او تستفسر عنها اضغط علي",
    },
    {
        "key": "luckybox", "label": "صندوق الحظ",
        "emoji": "🎁", "prefix": "LUCKY", "needs_username": False,
        "desc": "لو تبي تشتري صندوق حظ او تستفسر عن جوائزه اضغط علي",
    },
]
TICKET_PREFIXES = tuple(f"{c['prefix'].lower()}-" for c in TICKET_CATEGORIES)
TICKET_CATEGORY_BY_KEY = {c["key"]: c for c in TICKET_CATEGORIES}

processing_messages = set()
invites_cache = {}

# قنوات تم إشعارها بوضع "غير متوفر" حتى لا يتكرر الإشعار
away_notified_channels = set()


def is_ticket_channel(channel) -> bool:
    return bool(channel and getattr(channel, "name", "").startswith(TICKET_PREFIXES))


# =========================================================
# ============= تخزين آمن (بدون فقدان بيانات) =============
# =========================================================
# نستخدم كتابة ذرية (temp file + os.replace) بالإضافة إلى نسخة احتياطية .bak
# حتى لو انقطع البوت أو تم إيقافه بالقوة أثناء الكتابة، لن يتلف الملف الأصلي
# ولن تُفقد آخر نسخة سليمة من البيانات.

def _atomic_write_json(path: str, data: dict):
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # عملية ذرية على مستوى نظام الملفات
    except Exception as e:
        print(f"❌ خطأ أثناء الكتابة الآمنة إلى {path}: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return

    # نسخة احتياطية إضافية (لا توقف البرنامج إذا فشلت)
    try:
        with open(f"{path}.bak", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_json_with_backup(path: str):
    """يحاول تحميل الملف الأساسي، وإن كان تالفاً/مفقوداً يلجأ للنسخة الاحتياطية."""
    for candidate, is_backup in ((path, False), (f"{path}.bak", True)):
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            if is_backup:
                print(f"⚠️ الملف الأساسي {path} تالف أو مفقود، تم الاسترجاع من النسخة الاحتياطية.")
            return data
        except Exception as e:
            print(f"⚠️ تعذر قراءة {candidate}: {e}")
            continue
    return None


def load_config():
    data = _load_json_with_backup(CONFIG_FILE)
    if data is not None:
        return data
    return {
        "welcome_channel_id": DEFAULT_WELCOME_CHANNEL_ID,
        "reviews_channel_id": DEFAULT_REVIEWS_CHANNEL_ID,
        "tax_channel_id": DEFAULT_TAX_CHANNEL_ID,
        "buy_category_id": DEFAULT_BUY_CATEGORY_ID,
        "payment_methods": DEFAULT_PAYMENT_METHODS,
        "auto_reaction_channel_id": None,
        "auto_reaction_emoji": None,
        "away_mode": False,
        "away_reason": None,
        "ticket_counters": {},
        "invite_uses_snapshot": {},
        "fake_invite_min_days": 5,
        "away_notified_channels": [],
    }


def save_config(data):
    _atomic_write_json(CONFIG_FILE, data)


config = load_config()
_config_dirty = False
if "payment_methods" not in config:
    config["payment_methods"] = DEFAULT_PAYMENT_METHODS
    _config_dirty = True
if "auto_reaction_channel_id" not in config:
    config["auto_reaction_channel_id"] = None
    _config_dirty = True
if "auto_reaction_emoji" not in config:
    config["auto_reaction_emoji"] = None
    _config_dirty = True
if "away_mode" not in config:
    config["away_mode"] = False
    _config_dirty = True
if "away_reason" not in config:
    config["away_reason"] = None
    _config_dirty = True
if not config.get("tax_channel_id"):
    config["tax_channel_id"] = DEFAULT_TAX_CHANNEL_ID
    _config_dirty = True
if not config.get("buy_category_id"):
    config["buy_category_id"] = DEFAULT_BUY_CATEGORY_ID
    _config_dirty = True
if not config.get("welcome_channel_id"):
    config["welcome_channel_id"] = DEFAULT_WELCOME_CHANNEL_ID
    _config_dirty = True
if not config.get("reviews_channel_id"):
    config["reviews_channel_id"] = DEFAULT_REVIEWS_CHANNEL_ID
    _config_dirty = True
if "ticket_counters" not in config:
    config["ticket_counters"] = {}
    _config_dirty = True
if "invite_uses_snapshot" not in config:
    config["invite_uses_snapshot"] = {}
    _config_dirty = True
if "fake_invite_min_days" not in config:
    config["fake_invite_min_days"] = 5
    _config_dirty = True
if "away_notified_channels" not in config:
    config["away_notified_channels"] = []
    _config_dirty = True
if _config_dirty:
    save_config(config)

# نستعيد قنوات "الغياب" التي تم إشعارها قبل آخر إعادة تشغيل حتى لا يتكرر الإشعار
away_notified_channels = set(config.get("away_notified_channels", []))


def _persist_away_notified():
    config["away_notified_channels"] = list(away_notified_channels)
    save_config(config)


def get_next_ticket_number(prefix: str) -> int:
    counters = config.setdefault("ticket_counters", {})
    counters[prefix] = counters.get(prefix, 0) + 1
    save_config(config)
    return counters[prefix]


def load_sales_counter():
    data = _load_json_with_backup(SALES_COUNTER_FILE)
    if data is not None:
        try:
            return int(data.get("count", 0))
        except Exception:
            return 0
    return 0


def save_sales_counter(count: int):
    _atomic_write_json(SALES_COUNTER_FILE, {"count": count})


sales_counter = load_sales_counter()


def parse_amount(text: str):
    cleaned = text.strip().replace(",", "").lower()
    match = re.match(r"^(\d+(?:\.\d+)?)\s*([kmb])?$", cleaned)
    if not match:
        return None

    number, suffix = match.groups()
    val = float(number)

    if suffix == "k":
        val *= 1_000
    elif suffix == "m":
        val *= 1_000_000
    elif suffix == "b":
        val *= 1_000_000_000

    return val if val > 0 else None


# =========================================================
# ================= أدوات مشتركة (تأكيد / لوق) ============
# =========================================================

class ConfirmView(discord.ui.View):
    def __init__(self, author_id: int, on_confirm, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.on_confirm = on_confirm

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ **هذا التأكيد مخصص فقط لمن استخدم الأمر.**", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="تأكيد", emoji="✅", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard(interaction):
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        try:
            await self.on_confirm(interaction)
        except Exception as e:
            print(f"خطأ أثناء تنفيذ العملية بعد التأكيد: {e}")
        self.stop()

    @discord.ui.button(label="إلغاء", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._guard(interaction):
            return
        for child in self.children:
            child.disabled = True
        embed = discord.Embed(description="🚫 **تم إلغاء العملية.**", color=discord.Color.greyple())
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True


async def ask_confirmation(ctx_or_interaction, description: str, on_confirm, author_id: int):
    embed = discord.Embed(
        title="⚠️ تأكيد مطلوب",
        description=description,
        color=discord.Color.orange()
    )
    view = ConfirmView(author_id=author_id, on_confirm=on_confirm)
    await ctx_or_interaction.send(embed=embed, view=view)


async def generate_ticket_transcript(channel: discord.TextChannel) -> discord.File:
    """يجمع كل رسائل التذكرة في ملف txt واحد."""
    lines = [
        f"سجل محادثة التذكرة: #{channel.name}",
        f"آيدي القناة: {channel.id}",
        f"السيرفر: {channel.guild.name}",
        f"وقت الإنشاء: {discord.utils.utcnow().isoformat()}",
        "=" * 60,
        "",
    ]
    try:
        async for msg in channel.history(limit=None, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            author = f"{msg.author} ({msg.author.id})"
            content = msg.content or ""
            lines.append(f"[{timestamp}] {author}: {content}")
            for att in msg.attachments:
                lines.append(f"    📎 مرفق: {att.url}")
            for embed in msg.embeds:
                if embed.description:
                    lines.append(f"    [Embed] {embed.description}")
    except Exception as e:
        lines.append(f"\n[تعذر جلب بعض الرسائل: {e}]")

    text_data = "\n".join(lines)
    buffer = io.BytesIO(text_data.encode("utf-8"))
    filename = f"transcript-{channel.name}.txt"
    return discord.File(buffer, filename=filename)


EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE0F"
    "]+",
    flags=re.UNICODE
)


def strip_emojis(text: str) -> str:
    """يزيل الإيموجيات اليونيكود (والفاصل الاختياري) من النص."""
    if not text:
        return text
    cleaned = EMOJI_PATTERN.sub("", text)
    cleaned = re.sub(r"<a?:\w+:\d+>", "", cleaned)  # إيموجيات الديسكورد المخصصة
    return re.sub(r"[ \t]+", " ", cleaned).strip()


async def generate_messages_only_transcript(channel: discord.TextChannel) -> discord.File:
    """
    ترانسكريبت يحتوي على الرسائل النصية فقط (بدون إيموجيات، بدون مرفقات أو إيمبدات).
    يُستخدم مع أمر +transcript.
    """
    lines = []
    try:
        async for msg in channel.history(limit=None, oldest_first=True):
            content = strip_emojis(msg.content or "")
            if not content:
                continue
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"[{timestamp}] {msg.author}: {content}")
    except Exception as e:
        lines.append(f"[تعذر جلب بعض الرسائل: {e}]")

    text_data = "\n".join(lines) if lines else "لا توجد رسائل نصية."
    buffer = io.BytesIO(text_data.encode("utf-8"))
    filename = f"transcript-{channel.name}.txt"
    return discord.File(buffer, filename=filename)


async def log_ticket_transcript(channel: discord.TextChannel, closed_by: discord.abc.User):
    """يرسل ملف اللوق الكامل للتذكرة إلى روم اللوقات المخصص."""
    log_channel = channel.guild.get_channel(TICKET_LOG_CHANNEL_ID)
    if log_channel is None:
        print("⚠️ لم يتم العثور على قناة لوق التذاكر المحددة.")
        return
    try:
        file = await generate_ticket_transcript(channel)
        embed = discord.Embed(
            title="🧾 إغلاق تذكرة",
            description=(
                f"📌 **القناة:** `#{channel.name}`\n"
                f"🆔 **آيدي القناة:** `{channel.id}`\n"
                f"🔒 **أُغلقت بواسطة:** {closed_by.mention}"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Axion Store • Ticket Logs")
        embed.timestamp = discord.utils.utcnow()
        await log_channel.send(embed=embed, file=file)
    except Exception as e:
        print(f"خطأ أثناء إرسال ترانسكريبت التذكرة: {e}")


async def close_and_delete_ticket(channel: discord.TextChannel, closer: discord.abc.User):
    """منطق إغلاق وحذف التذكرة المشترك بين زر التحكم وأمر +close."""
    embed = discord.Embed(
        description="🔒 **تم إغلاق التذكرة، سيتم حذف القناة تلقائياً خلال 5 ثوانٍ...**",
        color=discord.Color.red()
    )
    try:
        await channel.send(embed=embed)
    except Exception:
        pass

    for target, overwrite in list(channel.overwrites.items()):
        if isinstance(target, discord.Member) and not target.bot:
            overwrite.send_messages = False
            try:
                await channel.set_permissions(target, overwrite=overwrite)
            except Exception:
                pass

    await log_ticket_transcript(channel, closer)

    away_notified_channels.discard(channel.id)
    _persist_away_notified()

    await asyncio.sleep(5)
    try:
        await channel.delete()
    except Exception:
        pass


# =========================================================
# ==================== كلاسات التذاكر ====================
# =========================================================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق وحذف التذكرة", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        closer = interaction.user

        async def do_close(confirm_interaction: discord.Interaction):
            await close_and_delete_ticket(channel, closer)

        embed = discord.Embed(
            title="⚠️ تأكيد الإغلاق",
            description="**هل أنت متأكد من إغلاق وحذف هذه التذكرة؟**\nسيتم حفظ نسخة كاملة من المحادثة قبل الحذف.",
            color=discord.Color.orange()
        )
        view = ConfirmView(author_id=closer.id, on_confirm=do_close)
        await interaction.response.send_message(embed=embed, view=view)

    @discord.ui.button(label="استلام التذكرة (Claim)", emoji="🙋‍♂️", style=discord.ButtonStyle.secondary, custom_id="claim_ticket_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description=f"✅ **تم استلام التذكرة بواسطة {interaction.user.mention}**\nسيقوم بمتابعة طلبك الآن.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


async def create_service_ticket(interaction: discord.Interaction, category: dict, extra_info: str = None):
    """ينشئ قناة تذكرة لقسم معين من TICKET_CATEGORIES."""
    guild = interaction.guild
    member = interaction.user
    prefix = category["prefix"]

    for channel in guild.text_channels:
        if is_ticket_channel(channel):
            overwrite = channel.overwrites_for(member)
            if overwrite.view_channel:
                embed = discord.Embed(
                    description=f"⚠️ **لديك تذكرة مفتوحة بالفعل!** {channel.mention}\nيمكنك فتح تذكرة واحدة فقط في نفس الوقت.",
                    color=discord.Color.orange()
                )
                if interaction.response.is_done():
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
    }

    for role in guild.roles:
        if role.permissions.administrator or role.id == BUY_ROLE_ID:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    cat_id = config.get("buy_category_id")
    ticket_category = guild.get_channel(cat_id) if cat_id else None

    if not ticket_category:
        ticket_category = discord.utils.get(guild.categories, name="TICKETS")
        if not ticket_category:
            try:
                ticket_category = await guild.create_category("TICKETS")
            except Exception:
                ticket_category = None

    number = get_next_ticket_number(prefix)
    channel_name = f"{prefix}-{number:04d}"

    try:
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=ticket_category,
            overwrites=overwrites
        )
    except discord.HTTPException as e:
        error_embed = discord.Embed(
            description=f"❌ **تعذر إنشاء التذكرة، حاول مرة أخرى أو تواصل مع الإدارة.**\n`{e}`",
            color=discord.Color.red()
        )
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return

    success_embed = discord.Embed(
        description=f"✅ **تم إنشاء تذكرتك بنجاح!**\n📩 {ticket_channel.mention}",
        color=discord.Color.green()
    )
    if interaction.response.is_done():
        await interaction.followup.send(embed=success_embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=success_embed, ephemeral=True)

    description = (
        f"**أهلاً بك {member.mention} في 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞 👋**\n\n"
        f"**📝 يرجى كتابة تفاصيل طلبك بوضوح وسيقوم الطاقم بالرد عليك فوراً.**\n"
        f"**⏱️ مدة التسليم المتوقعة: من دقيقة واحدة إلى 48 ساعة كحد أقصى.**"
    )
    if extra_info:
        description += f"\n\n{extra_info}"

    embed = discord.Embed(
        title=f"{category['emoji']} تذكرة {category['label']} - Axion Store",
        description=description,
        color=TICKET_EMBED_COLOR
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"{guild.name} • Axion Store", icon_url=guild.icon.url if guild.icon else None)
    embed.timestamp = discord.utils.utcnow()

    mention_content = f"{member.mention} <@&{BUY_ROLE_ID}>"
    await ticket_channel.send(content=mention_content, embed=embed, view=TicketControlView())

    if config.get("away_mode"):
        reason = config.get("away_reason") or "غير محدد"
        away_embed = discord.Embed(
            description=f"🌙 **البائع غير متوفر حالياً.**\n📌 **السبب:** {reason}\nسيتم الرد عليك في أقرب وقت ممكن، شكراً لصبرك.",
            color=discord.Color.orange()
        )
        await ticket_channel.send(embed=away_embed)
        away_notified_channels.add(ticket_channel.id)
        _persist_away_notified()

    try:
        notify_user = guild.get_member(TICKET_NOTIFY_USER_ID) or await guild.fetch_member(TICKET_NOTIFY_USER_ID)
    except Exception:
        notify_user = None

    if notify_user:
        notify_embed = discord.Embed(
            title="🎫 تذكرة جديدة تم فتحها",
            description=(
                f"👤 **العضو:** {member.mention} `({member.id})`\n"
                f"📌 **القسم:** {category['label']}\n"
                f"💬 **القناة:** {ticket_channel.mention}\n"
                f"🏠 **السيرفر:** {guild.name}"
            ),
            color=TICKET_EMBED_COLOR
        )
        notify_embed.timestamp = discord.utils.utcnow()
        try:
            await notify_user.send(embed=notify_embed)
        except Exception:
            pass


class RobuxUsernameModal(discord.ui.Modal, title="بيانات حساب الروبوكس"):
    username = discord.ui.TextInput(
        label="اكتب username حسابك هنا",
        placeholder="مثال: Player123",
        required=True,
        max_length=100
    )

    def __init__(self, category: dict):
        super().__init__()
        self.category = category

    async def on_submit(self, interaction: discord.Interaction):
        extra_info = f"🎮 **يوزر الروبوكس:** `{self.username.value.strip()}`"
        await create_service_ticket(interaction, self.category, extra_info=extra_info)


class ServiceTicketButton(discord.ui.Button):
    def __init__(self, category: dict, row: int = None):
        super().__init__(
            label=category["label"],
            emoji=category["emoji"],
            style=discord.ButtonStyle.primary,
            custom_id=f"ticket_btn_{category['key']}",
            row=row
        )
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        category = self.category
        if category.get("needs_username"):
            await interaction.response.send_modal(RobuxUsernameModal(category))
        else:
            await create_service_ticket(interaction, category)


class TicketSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for index, category in enumerate(TICKET_CATEGORIES):
            self.add_item(ServiceTicketButton(category, row=index // 3))


class ServiceTicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=category["label"],
                value=category["key"],
                emoji=category["emoji"],
                description=category["desc"][:100]
            )
            for category in TICKET_CATEGORIES
        ]
        super().__init__(
            placeholder="اختر نوع طلبك من هنا...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        category = TICKET_CATEGORY_BY_KEY.get(self.values[0])
        if not category:
            return
        if category.get("needs_username"):
            await interaction.response.send_modal(RobuxUsernameModal(category))
        else:
            await create_service_ticket(interaction, category)


class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ServiceTicketSelect())


# =========================================================
# ===================== البوت الرئيسي =====================
# =========================================================

class CustomBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.presences = True
        intents.message_content = True
        intents.invites = True
        super().__init__(command_prefix="+", intents=intents, help_command=None)

    async def setup_hook(self):
        self.add_view(TicketSetupView())
        self.add_view(TicketSelectView())
        self.add_view(TicketControlView())

bot = CustomBot()


@bot.check
async def restrict_to_admin(ctx: commands.Context):
    if ctx.guild is None:
        return False
    if ctx.command and ctx.command.name in ("close", "claim"):
        return True
    return ctx.author.guild_permissions.administrator


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply(embed=discord.Embed(description="❌ **عذراً، هذا الأمر مخصص فقط لإدارة السيرفر.**", color=discord.Color.red()), mention_author=False)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(embed=discord.Embed(description="⚠️ **الرجاء كتابة المعطى المطلوب بشكل صحيح.**", color=discord.Color.orange()), mention_author=False)
    elif isinstance(error, commands.BadArgument):
        await ctx.reply(embed=discord.Embed(description="⚠️ **تأكد من صحة البيانات أو المنشن المدخل.**", color=discord.Color.orange()), mention_author=False)
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"خطأ غير متوقع: {error}")


@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول بنجاح باسم: {bot.user}")
    activity = discord.Game(name="Axion Store | DEV BY : D0JW")
    await bot.change_presence(activity=activity)

    snapshot = config.setdefault("invite_uses_snapshot", {})
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invites_cache[guild.id] = invites
            # نأخذ لقطة أولية لعدد استخدامات كل رابط دعوة (تُستخدم لاحقاً لحساب مغادرة المدعوين)
            guild_snapshot = snapshot.setdefault(str(guild.id), {})
            for inv in invites:
                guild_snapshot.setdefault(inv.code, {"uses": inv.uses, "joins": [], "leaves": 0})
        except Exception:
            pass
    save_config(config)


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    inviter = None
    invite_code = None

    try:
        old_invites = invites_cache.get(guild.id, [])
        new_invites = await guild.invites()
        invites_cache[guild.id] = new_invites

        for old in old_invites:
            new = discord.utils.get(new_invites, code=old.code)
            if new and new.uses > old.uses:
                inviter = old.inviter
                invite_code = old.code
                break
    except Exception:
        pass

    # تسجيل عملية الانضمام مع رابط الدعوة المستخدم لأجل حساب المغادرين/الوهميين لاحقاً في +invites
    if invite_code:
        guild_snapshot = config.setdefault("invite_uses_snapshot", {}).setdefault(str(guild.id), {})
        entry = guild_snapshot.setdefault(invite_code, {"uses": 0, "joins": [], "leaves": 0})
        entry["joins"].append({
            "member_id": member.id,
            "joined_at": discord.utils.utcnow().isoformat(),
        })
        save_config(config)

    channel_id = config.get("welcome_channel_id", DEFAULT_WELCOME_CHANNEL_ID)
    channel = guild.get_channel(channel_id)
    if channel is None:
        return

    inv_text = f"📩 **تمت الدعوة بواسطة:** {inviter.mention}" if inviter else "📩 **تمت الدعوة بواسطة:** غير معروف"
    embed = discord.Embed(
        title="✨ عضو جديد انضم إلى 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞 ✨",
        description=f"مرحباً بك {member.mention} في **{guild.name}** 🌸\n{inv_text}",
        color=EMBED_COLOR
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="📊 الترتيب", value=f"العضو رقم **#{guild.member_count}**", inline=True)
    embed.add_field(name="📅 إنشاء الحساب", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    embed.set_footer(text=f"{guild.name} • Welcome System", icon_url=guild.icon.url if guild.icon else None)
    embed.timestamp = discord.utils.utcnow()

    await channel.send(content=f"🎉 {member.mention}", embed=embed)


@bot.event
async def on_member_remove(member: discord.Member):
    """يسجل مغادرة العضو مقابل رابط الدعوة الذي دخل به، لأجل إحصائية +invites (المغادرين)."""
    guild = member.guild
    guild_snapshot = config.setdefault("invite_uses_snapshot", {}).get(str(guild.id))
    if not guild_snapshot:
        return

    changed = False
    for code, entry in guild_snapshot.items():
        for j in entry.get("joins", []):
            if j.get("member_id") == member.id and not j.get("left"):
                j["left"] = True
                entry["leaves"] = entry.get("leaves", 0) + 1
                changed = True
                break

    if changed:
        save_config(config)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    if message.id in processing_messages:
        return
    processing_messages.add(message.id)

    try:
        if message.content.strip() == "شعار":
            await message.reply("𝐌𝐗 |", mention_author=False)

        tax_channel_id = config.get("tax_channel_id")
        if tax_channel_id and message.channel.id == tax_channel_id and not message.content.startswith("+"):
            amount = parse_amount(message.content)
            if amount is not None:
                total_with_tax = math.ceil(amount / 0.95)
                embed = discord.Embed(description=f"💳 **المبلغ مع الضريبة:**\n### `{total_with_tax:,}`", color=EMBED_COLOR)
                await message.reply(embed=embed, mention_author=False)

        auto_channel_id = config.get("auto_reaction_channel_id")
        auto_emoji = config.get("auto_reaction_emoji")
        if auto_channel_id and auto_emoji and message.channel.id == auto_channel_id:
            try:
                emoji_obj = discord.PartialEmoji.from_str(auto_emoji)
                await message.add_reaction(emoji_obj)
            except Exception as e:
                print(f"خطأ أثناء إضافة الريأكشن التلقائي: {e}")

        if (
            config.get("away_mode")
            and is_ticket_channel(message.channel)
            and not message.author.guild_permissions.administrator
            and message.channel.id not in away_notified_channels
            and not message.content.startswith("+")
        ):
            reason = config.get("away_reason") or "غير محدد"
            away_embed = discord.Embed(
                description=f"🌙 **البائع غير متوفر حالياً.**\n📌 **السبب:** {reason}\nسيتم الرد عليك في أقرب وقت ممكن، شكراً لصبرك.",
                color=discord.Color.orange()
            )
            await message.channel.send(embed=away_embed)
            away_notified_channels.add(message.channel.id)
            _persist_away_notified()

        await bot.process_commands(message)
    finally:
        processing_messages.discard(message.id)


@bot.event
async def on_guild_channel_delete(channel):
    """تنظيف قنوات الغياب المحذوفة من الذاكرة والملف حتى لا تتراكم بلا داعٍ."""
    if channel.id in away_notified_channels:
        away_notified_channels.discard(channel.id)
        _persist_away_notified()


# =========================================================
# ==================== الأوامر الكاملة =====================
# =========================================================

@bot.command(name="lock")
async def lock_channel(ctx: commands.Context):
    try: await ctx.message.delete()
    except Exception: pass
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(embed=discord.Embed(description="🔒 **تم قفل القناة بنجاح.**", color=discord.Color.red()))


@bot.command(name="unlock")
async def unlock_channel(ctx: commands.Context):
    try: await ctx.message.delete()
    except Exception: pass
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(embed=discord.Embed(description="🔓 **تم فتح القناة بنجاح.**", color=discord.Color.green()))


@bot.command(name="terms")
async def terms_command(ctx: commands.Context):
    try: await ctx.message.delete()
    except Exception: pass

    embed = discord.Embed(
        title="📜 قوانين متجر 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞",
        description=AXION_TERMS,
        color=EMBED_COLOR
    )
    embed.set_footer(text=f"{ctx.guild.name} • Axion Store", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.send(embed=embed)


@bot.command(name="claim")
async def claim_cmd(ctx: commands.Context):
    if not is_ticket_channel(ctx.channel):
        await ctx.reply(embed=discord.Embed(description="❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", color=discord.Color.red()), mention_author=False)
        return

    try: await ctx.message.delete()
    except Exception: pass

    embed = discord.Embed(
        title="🙋‍♂️ تم استلام التذكرة",
        description=f"**بواسطة:** {ctx.author.mention}\nسيقوم بمتابعة طلبك الآن.",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"{ctx.guild.name} • Axion Store", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.timestamp = discord.utils.utcnow()
    await ctx.send(embed=embed)


@bot.command(name="addto")
async def addto_command(ctx: commands.Context, member: discord.Member):
    if not is_ticket_channel(ctx.channel):
        await ctx.reply(embed=discord.Embed(description="❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", color=discord.Color.red()), mention_author=False)
        return

    try: await ctx.message.delete()
    except Exception: pass

    try:
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
    except Exception as e:
        await ctx.send(embed=discord.Embed(description=f"❌ **تعذر إضافة العضو:** {e}", color=discord.Color.red()))
        return

    await ctx.send(embed=discord.Embed(description=f"✅ **تم إضافة {member.mention} إلى هذه التذكرة.**", color=discord.Color.green()))


@bot.command(name="removeto")
async def removeto_command(ctx: commands.Context, member: discord.Member):
    if not is_ticket_channel(ctx.channel):
        await ctx.reply(embed=discord.Embed(description="❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", color=discord.Color.red()), mention_author=False)
        return

    try: await ctx.message.delete()
    except Exception: pass

    try:
        await ctx.channel.set_permissions(member, overwrite=None)
    except Exception as e:
        await ctx.send(embed=discord.Embed(description=f"❌ **تعذر إزالة العضو:** {e}", color=discord.Color.red()))
        return

    await ctx.send(embed=discord.Embed(description=f"🚫 **تمت إزالة {member.mention} من هذه التذكرة.**", color=discord.Color.red()))


@bot.command(name="invites")
async def check_invites(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author

    total_uses = 0
    invites = []
    try:
        invites = await ctx.guild.invites()
        for inv in invites:
            if inv.inviter == target:
                total_uses += inv.uses
    except Exception:
        pass

    # حساب المدعوين الذين غادروا السيرفر، والدعوات "الوهمية" (فاكة)
    # وهمية = عضو دخل عبر رابط هذا الشخص وغادر خلال فترة قصيرة جداً (أقل من الحد الأدنى بالأيام)
    left_count = 0
    fake_count = 0
    real_count = 0

    guild_snapshot = config.get("invite_uses_snapshot", {}).get(str(ctx.guild.id), {})
    my_invite_codes = {inv.code for inv in invites if inv.inviter and inv.inviter.id == target.id}

    for code in my_invite_codes:
        entry = guild_snapshot.get(code)
        if not entry:
            continue
        for j in entry.get("joins", []):
            if j.get("left"):
                left_count += 1
                fake_count += 1
            else:
                real_count += 1

    embed = discord.Embed(
        title="📊 إحصائية الدعوات",
        color=EMBED_COLOR
    )
    embed.description = f"**العضو:** {target.mention}"
    embed.add_field(name="✅ إجمالي الدعوات", value=f"`{total_uses}`", inline=True)
    embed.add_field(name="🟢 لا يزالون بالسيرفر", value=f"`{real_count}`", inline=True)
    embed.add_field(name="🚪 غادروا السيرفر", value=f"`{left_count}`", inline=True)
    embed.add_field(name="⚠️ دعوات وهمية (Fake)", value=f"`{fake_count}`", inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text=f"{ctx.guild.name} • Invites System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="close")
async def close_ticket_cmd(ctx: commands.Context):
    if not is_ticket_channel(ctx.channel):
        await ctx.reply(embed=discord.Embed(description="❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", color=discord.Color.red()), mention_author=False)
        return

    channel = ctx.channel
    closer = ctx.author

    async def do_close(confirm_interaction: discord.Interaction):
        await close_and_delete_ticket(channel, closer)

    await ask_confirmation(
        ctx,
        "**هل أنت متأكد من إغلاق وحذف هذه التذكرة؟**\nسيتم حفظ نسخة كاملة من المحادثة قبل الحذف.",
        do_close,
        author_id=closer.id
    )


@bot.command(name="transcript")
async def transcript_command(ctx: commands.Context):
    """يصدّر رسائل التذكرة الحالية فقط (بدون إيموجيات، بدون مرفقات/إيمبدات) كملف نصي."""
    if not is_ticket_channel(ctx.channel):
        await ctx.reply(embed=discord.Embed(description="❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", color=discord.Color.red()), mention_author=False)
        return

    try:
        await ctx.message.delete()
    except Exception:
        pass

    status = await ctx.send(embed=discord.Embed(description="⏳ **جاري تجهيز نسخة الرسائل...**", color=EMBED_COLOR))
    file = await generate_messages_only_transcript(ctx.channel)
    await status.delete()
    await ctx.send(
        embed=discord.Embed(description="📄 **تم تجهيز نسخة الرسائل النصية لهذه التذكرة.**", color=discord.Color.green()),
        file=file
    )


@bot.command(name="kl")
async def kl_warning(ctx: commands.Context):
    if not is_ticket_channel(ctx.channel):
        await ctx.reply(embed=discord.Embed(description="❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", color=discord.Color.red()), mention_author=False)
        return

    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        description="⚠️ **في حالة عدم وجود رد لمدة تتراوح ما بين 30 إلى 60 دقيقة، سيتم إغلاق التذكرة تلقائياً.**",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)


@bot.command(name="bnm")
async def set_ticket_category(ctx: commands.Context, category_id: int):
    category = ctx.guild.get_channel(category_id)
    if category is None or not isinstance(category, discord.CategoryChannel):
        await ctx.reply(embed=discord.Embed(description="❌ **لم يتم العثور على الكاتيجوري (Category) المحددة.**", color=discord.Color.red()), mention_author=False)
        return

    config["buy_category_id"] = category.id
    save_config(config)
    await ctx.reply(embed=discord.Embed(description=f"✅ **تم اعتماد الكاتيجوري `{category.name}` لجميع التذاكر.**", color=discord.Color.green()), mention_author=False)


@bot.command(name="auto-setup")
async def auto_setup(ctx: commands.Context, channel_id: int, emoji: str):
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.reply(embed=discord.Embed(description="❌ **لم يتم العثور على القناة المحددة.**", color=discord.Color.red()), mention_author=False)
        return

    try:
        parsed_emoji = discord.PartialEmoji.from_str(emoji)
    except Exception:
        await ctx.reply(embed=discord.Embed(description="❌ **الإيموجي المدخل غير صالح.**", color=discord.Color.red()), mention_author=False)
        return

    config["auto_reaction_channel_id"] = channel.id
    config["auto_reaction_emoji"] = str(parsed_emoji)
    save_config(config)

    await ctx.reply(
        embed=discord.Embed(
            description=f"✅ **تم تفعيل الرياكشن التلقائي {parsed_emoji} على كل رسالة في {channel.mention}**",
            color=discord.Color.green()
        ),
        mention_author=False
    )


@bot.command(name="away")
async def away_command(ctx: commands.Context, *, reason: str = None):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if reason and reason.strip().lower() in ("off", "back", "رجعت"):
        config["away_mode"] = False
        config["away_reason"] = None
        save_config(config)
        away_notified_channels.clear()
        _persist_away_notified()
        await ctx.send(embed=discord.Embed(description="🟢 **تم إلغاء وضع الغياب، أنت متوفر الآن.**", color=discord.Color.green()))
        return

    config["away_mode"] = True
    config["away_reason"] = reason.strip() if reason else "غير محدد"
    save_config(config)
    away_notified_channels.clear()
    _persist_away_notified()

    await ctx.send(embed=discord.Embed(description=f"🌙 **تم تفعيل وضع الغياب.**\n📌 **السبب:** {config['away_reason']}\nسيتم إشعار العملاء تلقائياً في التذاكر.", color=discord.Color.orange()))


@bot.command(name="stats")
async def stats_command(ctx: commands.Context):
    guild = ctx.guild
    open_tickets = sum(1 for ch in guild.text_channels if is_ticket_channel(ch))

    per_category_lines = []
    counters = config.get("ticket_counters", {})
    for category in TICKET_CATEGORIES:
        total_opened = counters.get(category["prefix"], 0)
        currently_open = sum(1 for ch in guild.text_channels if ch.name.startswith(f"{category['prefix'].lower()}-"))
        per_category_lines.append(f"{category['emoji']} **{category['label']}:** فُتحت `{total_opened}` | مفتوحة الآن `{currently_open}`")

    embed = discord.Embed(
        title="📊 إحصائيات المتجر",
        color=TICKET_EMBED_COLOR
    )
    embed.add_field(name="💰 إجمالي المبيعات المسجلة", value=f"`{sales_counter}`", inline=True)
    embed.add_field(name="🎫 إجمالي التذاكر المفتوحة حالياً", value=f"`{open_tickets}`", inline=True)
    embed.add_field(name="👥 عدد أعضاء السيرفر", value=f"`{guild.member_count}`", inline=True)
    embed.add_field(name="📂 تفصيل الأقسام", value="\n".join(per_category_lines) or "لا يوجد بيانات بعد.", inline=False)
    embed.set_footer(text=f"{guild.name} • Axion Store", icon_url=guild.icon.url if guild.icon else None)
    embed.timestamp = discord.utils.utcnow()
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="find")
async def find_command(ctx: commands.Context, *, query: str):
    query_lower = query.lower().strip()

    matches = []
    for m in ctx.guild.members:
        candidates = [m.name.lower()]
        if m.nick:
            candidates.append(m.nick.lower())
        if getattr(m, "global_name", None):
            candidates.append(m.global_name.lower())
        if query_lower in candidates or any(query_lower in c for c in candidates) or query_lower == str(m.id):
            matches.append(m)

    matches = matches[:15]

    if not matches:
        await ctx.reply(embed=discord.Embed(description=f"❌ **لم يتم العثور على أي عميل يطابق:** `{query}`", color=discord.Color.red()), mention_author=False)
        return

    description = "\n".join(f"• {m.mention} — `{m}` (`{m.id}`)" for m in matches)
    embed = discord.Embed(
        title=f"🔎 نتائج البحث عن: {query}",
        description=description,
        color=TICKET_EMBED_COLOR
    )
    embed.set_footer(text=f"تم العثور على {len(matches)} نتيجة (حد أقصى 15)")
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="clear")
async def clear_messages(ctx: commands.Context, amount: int = 100):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    channel = ctx.channel

    async def do_clear(confirm_interaction: discord.Interaction):
        deleted = await channel.purge(limit=amount)
        msg = await channel.send(embed=discord.Embed(description=f"🧹 **تم مسح `{len(deleted)}` رسالة بنجاح.**", color=EMBED_COLOR))
        await asyncio.sleep(3)
        try:
            await msg.delete()
        except Exception:
            pass

    await ask_confirmation(
        ctx,
        f"**هل أنت متأكد من حذف حتى `{amount}` رسالة من هذه القناة؟**\nلا يمكن التراجع عن هذا الإجراء.",
        do_clear,
        author_id=ctx.author.id
    )


@bot.command(name="cus")
async def give_customer_role(ctx: commands.Context, member: discord.Member):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    role = ctx.guild.get_role(CUSTOMER_ROLE_ID)
    if role is None:
        await ctx.send(embed=discord.Embed(description="❌ **لم يتم العثور على رتبة العميل في السيرفر.**", color=discord.Color.red()))
        return

    if role in member.roles:
        await ctx.send(embed=discord.Embed(description=f"⚠️ {member.mention} **يمتلك الرتبة بالفعل!**", color=discord.Color.orange()))
        return

    try:
        await member.add_roles(role)
        await ctx.send(embed=discord.Embed(description=f"✨ **تم منح رتبة {role.mention} إلى {member.mention} بنجاح!** 🎉", color=EMBED_COLOR))
    except discord.Forbidden:
        await ctx.send(embed=discord.Embed(description="❌ **البوت لا يملك صلاحية لإعطاء هذه الرتبة.**", color=discord.Color.red()))
    except Exception as e:
        await ctx.send(embed=discord.Embed(description=f"❌ **حدث خطأ:** {e}", color=discord.Color.red()))


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="⚙️ لوحة الأوامر والتحكم الكاملة",
        description="البريفكس المعتمد: `+` لجميع الأوامر.\n*معظم الأوامر مخصصة لإدارة السيرفر (باستثناء `+close`, `+claim`).*",
        color=EMBED_COLOR,
    )

    embed.add_field(
        name="👑 الأوامر الإدارية العامة",
        value=(
            "`+clear <عدد>` • تنظيف ومسح الرسائل (يتطلب تأكيد)\n"
            "`+lock` / `+unlock` • قفل أو فتح القناة\n"
            "`+cus <@العضو>` • منح رتبة العميل فوراً\n"
            "`+come <@العضو>` • استدعاء عضو إلى القناة\n"
            "`+font <النص>` • زخرفة النصوص بشكل احترافي\n"
            "`+say <الرسالة>` • إرسال نص أو صورة (أو الاثنين) باسم البوت\n"
            "`+say-embed <الرسالة>` • إرسال إيمبد منسق\n"
            "`+find <اسم/آيدي>` • البحث عن عميل داخل السيرفر\n"
            "`+stats` • إحصائيات المتجر والتذاكر\n"
            "`+invites [@عضو]` • عدد الدعوات، المغادرين، والدعوات الوهمية\n"
            "`+transcript` • تصدير رسائل التذكرة الحالية فقط (بدون إيموجيات) كملف نصي\n"
            "`+away [سبب/off]` • تفعيل أو إلغاء وضع الغياب"
        ),
        inline=False
    )
    embed.add_field(
        name="🛍️ إعدادات المتجر والتذاكر",
        value=(
            "`+panel` • إرسال لوحة فتح التذاكر (أزرار)\n"
            "`+dpanel` • إرسال لوحة فتح التذاكر (قائمة اختيار Dropdown)\n"
            "`+claim` • استلام التذكرة الحالية\n"
            "`+close` • إغلاق التذكرة الحالية (يتطلب تأكيد + يحفظ لوق كامل)\n"
            "`+kl` • تحذير بالإغلاق التلقائي\n"
            "`+addto <@عضو>` • إضافة عضو للتذكرة الحالية\n"
            "`+removeto <@عضو>` • إزالة عضو من التذكرة الحالية\n"
            "`+terms` • عرض قوانين المتجر\n"
            "`+bnm <ID>` • تعيين كاتيجوري التذاكر\n"
            "`+setpay` • إعداد وتحديث طرق الدفع\n"
            "`+pay` • عرض طرق الدفع الحالية (مع أزرار نسخ سريعة)\n"
            "`+tax [ID]` • تعيين روم حساب الضريبة\n"
            "`+auto-setup <ID> <إيموجي>` • تفعيل ريأكشن تلقائي على قناة معينة\n"
            "`+rate <@المشتري> <المنتج>` • طلب تقييم من المشتري\n"
            "`+rate-setup <ID>` • تعيين روم التقييمات\n"
            "`+setup-welcome <ID>` • تعيين روم الترحيب"
        ),
        inline=False
    )
    embed.add_field(
        name="💰 نظام المبيعات",
        value=(
            "`+sold <@المشتري> \"المنتج\"` • تسجيل عملية بيع، إرسالها لقناة المبيعات، وطلب تقييم تلقائياً من المشتري مباشرة\n"
            "(ضع اسم المنتج بين علامتي اقتباس إن كان يحتوي على أكثر من كلمة)"
        ),
        inline=False
    )
    embed.add_field(
        name="🎁 صندوق الحظ",
        value=(
            "`+luckybox <@العضو>` • صندوق حظ مخصص لعضو معيّن فقط\n"
            "`+luckybox` (بدون منشن) • صندوق حظ عام، أول من يضغط الزر يفوز\n"
            "`+luckyinfo [@المشتري]` • إرسال شرح بكل جوائز صندوق الحظ ونسبها"
        ),
        inline=False
    )
    embed.add_field(
        name="📢 البرودكاست",
        value=(
            "`+bc <@العضو> <الرسالة>` • رسالة خاصة لشخص واحد\n"
            "`+bcall <الرسالة>` • رسالة خاصة للجميع (يتطلب تأكيد)\n"
            "`+bc-role <@الرتبة> <الرسالة>` • رسالة خاصة لرتبة محددة (يتطلب تأكيد)\n"
            "`+bc_online <الرسالة>` • رسالة للمتواجدين أونلاين (يتطلب تأكيد)"
        ),
        inline=False
    )
    embed.set_footer(text=f"{ctx.guild.name} • Control Panel", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="tax", aliases=["tax-setup"])
async def tax_setup(ctx: commands.Context, room_id: int = None):
    channel = ctx.guild.get_channel(room_id) if room_id else ctx.channel
    if channel is None:
        await ctx.reply(embed=discord.Embed(description="❌ **لم يتم العثور على القناة المحددة.**", color=discord.Color.red()), mention_author=False)
        return

    config["tax_channel_id"] = channel.id
    save_config(config)
    await ctx.reply(embed=discord.Embed(description=f"✅ **تم اعتماد قناة {channel.mention} لحساب الضريبة تلقائياً.**", color=discord.Color.green()), mention_author=False)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    await ctx.reply(embed=discord.Embed(description=f"⚡ **سرعة الاستجابة:** `{latency}ms`", color=EMBED_COLOR), mention_author=False)


@bot.command(name="serverinfo")
async def serverinfo(ctx: commands.Context):
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 معلومات السيرفر: {guild.name}", color=EMBED_COLOR)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👥 الأعضاء", value=f"**{guild.member_count}**", inline=True)
    embed.add_field(name="👑 المالك", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="📅 تاريخ الإنشاء", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
    embed.set_footer(text=f"{guild.name} • Axion Store")
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="font")
async def font_text(ctx: commands.Context, *, text: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    normal_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    fancy_chars  = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"

    trans_table = str.maketrans(normal_chars, fancy_chars)
    fancy_result = text.translate(trans_table)

    embed = discord.Embed(
        title="✨ زخرفة النصوص",
        description=f"**الـنـص الأصـلـي:**\n```{text}```\n**الـنـص المـزخـرف:**\n```{fancy_result}```",
        color=EMBED_COLOR
    )
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="come")
async def come_command(ctx: commands.Context, member: discord.Member):
    channel_link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}"

    embed = discord.Embed(
        title="📩 استدعاء مباشر",
        description=(
            f"مرحباً {member.mention} 👋\n\n"
            f"فريق الإدارة بانتظارك في الروم التالي:\n"
            f"📌 **[{ctx.channel.name}]({channel_link})**\n\n"
            f"يرجى التوجه إلى القناة في أقرب وقت."
        ),
        color=EMBED_COLOR
    )
    embed.set_footer(text=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.timestamp = discord.utils.utcnow()

    try:
        await member.send(embed=embed)
        await ctx.reply(embed=discord.Embed(description=f"✅ **تم إرسال الإشعار بنجاح إلى {member.mention}**", color=discord.Color.green()), mention_author=False)
    except discord.Forbidden:
        await ctx.reply(embed=discord.Embed(description=f"❌ **تعذر الإرسال لـ {member.mention} (الخاص مقفل).**", color=discord.Color.red()), mention_author=False)


@bot.command(name="setup-welcome")
async def setup_welcome(ctx: commands.Context, channel_id: int):
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.reply(embed=discord.Embed(description="❌ **لم يتم العثور على القناة المحددة.**", color=discord.Color.red()), mention_author=False)
        return

    config["welcome_channel_id"] = channel.id
    save_config(config)
    await ctx.reply(embed=discord.Embed(description=f"✅ **تم حفظ {channel.mention} كقناة رسمية للترحيب.**", color=discord.Color.green()), mention_author=False)


@bot.command(name="rate-setup")
async def rate_setup(ctx: commands.Context, channel_id: int):
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.reply(embed=discord.Embed(description="❌ **لم يتم العثور على القناة المحددة.**", color=discord.Color.red()), mention_author=False)
        return

    config["reviews_channel_id"] = channel.id
    save_config(config)
    await ctx.reply(embed=discord.Embed(description=f"✅ **تم حفظ {channel.mention} كقناة رسمية للتقييمات.**", color=discord.Color.green()), mention_author=False)


# =========================================================
# ==================== نظام الدفع (+pay / +setpay) ==================
# =========================================================

class SetPayModal(discord.ui.Modal, title="تحديث طرق الدفع"):
    libyana = discord.ui.TextInput(label="رقم ليبيانا", placeholder="أدخل الرقم...", required=False)
    madar = discord.ui.TextInput(label="رقم المدار", placeholder="أدخل الرقم...", required=False)
    binance = discord.ui.TextInput(label="بايننس (Binance)", placeholder="أدخل العنوان...", required=False)
    ltc = discord.ui.TextInput(label="عنوان لايتكوين (LTC)", placeholder="أدخل العنوان...", required=False)
    credit = discord.ui.TextInput(label="رصيد / كريديت", placeholder="أدخل البيانات...", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        config["payment_methods"] = {
            "ليبيانا": self.libyana.value.strip() or "لايوجد",
            "مدار": self.madar.value.strip() or "لايوجد",
            "بايننس": self.binance.value.strip() or "لايوجد",
            "LTC": self.ltc.value.strip() or "لايوجد",
            "كريديت": self.credit.value.strip() or "لايوجد"
        }
        save_config(config)
        await interaction.response.send_message("✅ **تم تحديث بيانات طرق الدفع بنجاح!**", ephemeral=True)


class SetPayView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id

    @discord.ui.button(label="✏️ تعديل طرق الدفع", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ **هذا الزر مخصص لمن استخدم الأمر فقط.**", ephemeral=True)
            return
        await interaction.response.send_modal(SetPayModal())


class PayCopyButton(discord.ui.Button):
    """زر يرسل رسالة خاصة (ephemeral) تحتوي بيانات طريقة دفع واحدة داخل كود بلوك لتسهيل نسخها."""
    def __init__(self, display_name: str, value: str):
        super().__init__(
            label=f"نسخ {display_name}",
            emoji="📋",
            style=discord.ButtonStyle.secondary
        )
        self.value = value
        self.display_name = display_name

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"📋 **{self.display_name}:**\n```{self.value}```",
            ephemeral=True
        )


class PayCopyView(discord.ui.View):
    def __init__(self, payments: dict, timeout: int = 300):
        super().__init__(timeout=timeout)
        pay_labels = [
            ("ليبيانا", "📱 ليبيانا"),
            ("مدار", "📱 مدار"),
            ("بايننس", "🟡 بايننس"),
            ("LTC", "🏛️ LTC"),
            ("كريديت", "💳 كريديت"),
        ]
        for key, display_name in pay_labels:
            self.add_item(PayCopyButton(display_name, payments.get(key, "لايوجد")))


@bot.command(name="setpay")
async def setpay_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    view = SetPayView(author_id=ctx.author.id)
    await ctx.send(embed=discord.Embed(description="⚙️ **اضغط على الزر لتعديل بيانات طرق الدفع الخاصة بالمتجر:**", color=EMBED_COLOR), view=view)


@bot.command(name="pay")
async def pay_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    payments = config.get("payment_methods", DEFAULT_PAYMENT_METHODS)

    embed = discord.Embed(
        title="💳 طرق الدفع المعتمدة",
        description=(
            "**يرجى اختيار طريقة الدفع المناسبة وتحويل المبلغ المطلوب.**\n"
            "اضغط على أي زر بالأسفل ⬇️ لنسخ بياناتها مباشرة بشكل خاص."
        ),
        color=EMBED_COLOR
    )
    embed.add_field(name="📱 ليبيانا", value=f"`{payments.get('ليبيانا', 'لايوجد')}`", inline=False)
    embed.add_field(name="📱 مدار", value=f"`{payments.get('مدار', 'لايوجد')}`", inline=False)
    embed.add_field(name="🟡 بايننس", value=f"`{payments.get('بايننس', 'لايوجد')}`", inline=False)
    embed.add_field(name="🏛️ LTC", value=f"`{payments.get('LTC', 'لايوجد')}`", inline=False)
    embed.add_field(name="💳 كريديت", value=f"`{payments.get('كريديت', 'لايوجد')}`", inline=False)
    embed.set_footer(text="يرجى إرسال صورة الإثبات داخل التذكرة بعد التحويل.")

    await ctx.send(embed=embed, view=PayCopyView(payments))


@bot.command(name="panel")
async def panel_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    categories_lines = "\n\n".join(
        f"{cat['emoji']} **{cat['label']}**\n{cat['desc']}" for cat in TICKET_CATEGORIES
    )

    embed = discord.Embed(
        title="🎫 مركز الطلبات والاستفسارات - 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞",
        description=(
            "**أهلاً بك في متجر Axion Store! 👋**\n"
            "اختر القسم المناسب لطلبك من الأزرار بالأسفل وسيتم فتح تذكرة خاصة بك فوراً.\n\n"
            f"{categories_lines}\n\n"
            "**⚠️ ملاحظة: يحق لك فتح تذكرة واحدة فقط في نفس الوقت.**"
        ),
        color=TICKET_EMBED_COLOR
    )
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text="Axion Store • DEV BY : @D0JW")
    embed.timestamp = discord.utils.utcnow()

    await ctx.send(embed=embed, view=TicketSetupView())


@bot.command(name="dpanel")
async def dpanel_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    categories_lines = "\n\n".join(
        f"{cat['emoji']} **{cat['label']}**\n{cat['desc']}" for cat in TICKET_CATEGORIES
    )

    embed = discord.Embed(
        title="🎫 مركز الطلبات والاستفسارات - 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞",
        description=(
            "**أهلاً بك في متجر Axion Store! 👋**\n\n"
            f"{categories_lines}\n\n"
            "**📥 اختر نوع طلبك من القائمة أدناه وسيتم فتح تذكرة خاصة بك فوراً.**\n"
            "**⚠️ ملاحظة: يحق لك فتح تذكرة واحدة فقط في نفس الوقت.**"
        ),
        color=TICKET_EMBED_COLOR
    )
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text="Axion Store • DEV BY : @D0JW")
    embed.timestamp = discord.utils.utcnow()

    await ctx.send(embed=embed, view=TicketSelectView())


# =========================================================
# ================= نظام التقييمات: +rate ==================
# =========================================================

class RateModal(discord.ui.Modal, title="تقييم الخدمة"):
    rating = discord.ui.TextInput(label="التقييم (من 1 إلى 5)", placeholder="5", max_length=1, required=True)
    comment = discord.ui.TextInput(label="رأيك بالخدمة", style=discord.TextStyle.paragraph, placeholder="اكتب انطباعك هنا...", required=True, max_length=300)

    def __init__(self, seller: discord.Member, buyer: discord.Member, product: str, view: "RateView"):
        super().__init__()
        self.seller = seller
        self.buyer = buyer
        self.product = product
        self.rate_view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            stars_count = int(self.rating.value)
            stars_count = max(1, min(5, stars_count))
        except ValueError:
            stars_count = 5

        stars = STAR_EMOJI * stars_count

        embed = discord.Embed(
            description=(
                f"**تم التقييم بواسطة:** {self.buyer.mention}\n\n"
                f"👤 **البائع:** {self.seller.mention}\n"
                f"🛍️ **المنتج:** `{self.product}`\n\n"
                f"🌟 **التقييم:** {stars}\n\n"
                f"💬 **التعليق:**\n```{self.comment.value}```"
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text="نظام التقييمات المعتمد • Axion Store")
        embed.timestamp = discord.utils.utcnow()

        reviews_channel_id = config.get("reviews_channel_id", DEFAULT_REVIEWS_CHANNEL_ID)
        reviews_channel = interaction.client.get_channel(reviews_channel_id)
        if reviews_channel:
            await reviews_channel.send(embed=embed)
            await interaction.response.send_message("✅ **شكراً جزيلاً على تقييمك!**", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ **لم يتم العثور على قناة التقييمات.**", ephemeral=True)

        # نعطّل الزر ونحدّث تسميته على الرسالة الأصلية مباشرة (بدل الاعتماد على
        # interaction.message الذي قد لا يكون متوفراً في بعض حالات المودال)
        self.rate_view.rate_button.disabled = True
        self.rate_view.rate_button.label = "تم التقييم بنجاح ✅"
        target_message = self.rate_view.message or interaction.message
        if target_message:
            try:
                await target_message.edit(view=self.rate_view)
            except Exception as e:
                print(f"⚠️ تعذر تحديث زر التقييم بعد الإرسال: {e}")


class RateView(discord.ui.View):
    def __init__(self, seller: discord.Member, buyer: discord.Member, product: str):
        super().__init__(timeout=None)
        self.seller = seller
        self.buyer = buyer
        self.product = product
        self.message = None  # يُضبط بعد إرسال الرسالة حتى يمكن تعديلها لاحقاً بأمان

    @discord.ui.button(label="⭐ قيّم تجربتك الآن", style=discord.ButtonStyle.success, emoji="🌟")
    async def rate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer.id:
            await interaction.response.send_message("❌ **هذا التقييم مخصص للمشتري فقط.**", ephemeral=True)
            return
        await interaction.response.send_modal(RateModal(self.seller, self.buyer, self.product, self))


def build_rate_request_embed(guild: discord.Guild, buyer: discord.Member, seller: discord.Member, product: str) -> discord.Embed:
    """رسالة طلب التقييم التي تصل للمشتري (مختلفة عن الرسالة التي تُنشر في روم التقييمات)."""
    embed = discord.Embed(
        title="🌟 شاركنا رأيك في تجربتك معنا!",
        description=(
            f"أهلاً بك {buyer.mention} 👋\n\n"
            f"**شكراً لثقتك في 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞!** نتمنى أن تكون تجربتك ممتازة.\n"
            f"رأيك يهمنا كثيراً ويساعدنا على تقديم خدمة أفضل، خذ لحظة من وقتك للتقييم 🙏"
        ),
        color=discord.Color.gold()
    )
    embed.add_field(name="🛍️ المنتج", value=f"`{product}`", inline=True)
    embed.add_field(name="🧑‍💼 تم البيع بواسطة", value=seller.mention, inline=True)
    embed.add_field(
        name="📝 كيف أقيّم؟",
        value="اضغط على الزر بالأسفل ⬇️ واختر عدد النجوم مع كتابة تعليق قصير عن تجربتك.",
        inline=False
    )
    embed.set_thumbnail(url=buyer.display_avatar.url)
    embed.set_footer(text=f"{guild.name} • Axion Store", icon_url=guild.icon.url if guild.icon else None)
    embed.timestamp = discord.utils.utcnow()
    return embed


async def send_rate_request(ctx: commands.Context, seller: discord.Member, buyer: discord.Member, product: str):
    """يبني ويرسل طلب التقييم، ويربط الرسالة بالـ View حتى يعمل تعديل الزر لاحقاً بشكل موثوق."""
    view = RateView(seller=seller, buyer=buyer, product=product)
    embed = build_rate_request_embed(ctx.guild, buyer, seller, product)
    sent_message = await ctx.send(content=buyer.mention, embed=embed, view=view)
    view.message = sent_message
    return sent_message


@bot.command(name="rate")
async def rate_prefix(ctx: commands.Context, buyer: discord.Member, *, product: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    await send_rate_request(ctx, seller=ctx.author, buyer=buyer, product=product)


# =========================================================
# =================== نظام تسجيل المبيعات: +sold ===================
# =========================================================

@bot.command(name="sold")
async def sold_command(ctx: commands.Context, buyer: discord.Member, *, product: str):
    """
    الاستخدام: +sold @المشتري اسم المنتج
    (المنشن أولاً، ثم اسم المنتج بعده - بدون الحاجة لعلامات اقتباس حتى لو كان أكثر من كلمة)
    بعد تسجيل عملية البيع بنجاح، يرسل البوت تلقائياً طلب تقييم للمشتري.
    """
    global sales_counter

    try:
        await ctx.message.delete()
    except Exception:
        pass

    product = product.strip()
    if not product:
        await ctx.send(embed=discord.Embed(description="⚠️ **يجب كتابة اسم المنتج.**\nمثال: `+sold @المشتري اسم المنتج`", color=discord.Color.orange()), delete_after=8)
        return

    sales_counter += 1
    save_sales_counter(sales_counter)
    order_number = f"AX-{sales_counter:05d}"

    embed = discord.Embed(
        title="🧾 تأكيد عملية بيع جديدة",
        description=f"تم إتمام عملية بيع بنجاح عبر **𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞**",
        color=discord.Color.from_rgb(46, 204, 113)
    )
    embed.add_field(name="🏷️ المنتج", value=f"```{product}```", inline=False)
    embed.add_field(name="👤 المشتري", value=buyer.mention, inline=True)
    embed.add_field(name="🧑‍💼 البائع", value=ctx.author.mention, inline=True)
    embed.add_field(name="🔢 رقم العملية", value=f"`{order_number}`", inline=False)
    embed.set_thumbnail(url=buyer.display_avatar.url)
    embed.set_author(name="Axion Store • Sales System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.set_footer(text=f"{ctx.guild.name} • تم التسجيل بواسطة {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    embed.timestamp = discord.utils.utcnow()

    # نرسل تأكيد عملية البيع دائماً في القناة الحالية (حتى لو تعذّر إرسال الويبهوك)
    # حتى لا تضيع تفاصيل العملية.
    await ctx.send(embed=embed)

    webhook_sent = False
    if SOLD_WEBHOOK_URL:
        try:
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(SOLD_WEBHOOK_URL, session=session)
                await webhook.send(
                    embed=embed,
                    username="Axion Store | Sales",
                    avatar_url=ctx.guild.icon.url if ctx.guild.icon else None
                )
            webhook_sent = True
        except Exception as e:
            webhook_sent = False
            print(f"خطأ أثناء إرسال ويبهوك عملية البيع: {e}")

    status_text = f"✅ **تم تسجيل عملية البيع بنجاح، رقم العملية:** `{order_number}`"
    if SOLD_WEBHOOK_URL and not webhook_sent:
        status_text = f"⚠️ **تم تسجيل عملية البيع رقم `{order_number}` بنجاح هنا، لكن تعذر إرسال نسخة عبر الويبهوك.**"
    await ctx.send(embed=discord.Embed(description=status_text, color=discord.Color.green() if webhook_sent or not SOLD_WEBHOOK_URL else discord.Color.orange()))

    # إرسال طلب تقييم تلقائي للمشتري مباشرة بعد تسجيل عملية البيع
    try:
        await send_rate_request(ctx, seller=ctx.author, buyer=buyer, product=product)
    except Exception as e:
        print(f"خطأ أثناء إرسال طلب التقييم التلقائي: {e}")


# =========================================================
# =================== صندوق الحظ: +luckybox ===================
# =========================================================

# الترتيب من الأكثر شيوعاً (أعلى نسبة) إلى الأندر (أقل نسبة)، ومجموع النسب = 100%
LUCKY_BOX_PRIZES = [
    {"name": "1M Credit", "weight": 60},
    {"name": "Hype Squad", "weight": 25},
    {"name": "5M Credit", "weight": 10},
    {"name": "10M Credit", "weight": 3},
    {"name": "Nitro", "weight": 1.5},
    {"name": "1B Credit", "weight": 0.5},
]


def draw_lucky_box_prize() -> dict:
    weights = [p["weight"] for p in LUCKY_BOX_PRIZES]
    return random.choices(LUCKY_BOX_PRIZES, weights=weights, k=1)[0]


def build_luckybox_intro_embed(guild: discord.Guild, gifter: discord.abc.User, recipient: discord.Member = None) -> discord.Embed:
    """الإيمبد الأولي: يعرض معلومات صندوق الحظ ونسب الجوائز قبل الفتح."""
    odds_lines = "\n".join(f"• **{p['name']}** — `{p['weight']}%`" for p in LUCKY_BOX_PRIZES)

    if recipient is not None:
        description = (
            f"{recipient.mention} **وصلك صندوق حظ من {gifter.mention}!**\n"
            f"اضغط على الزر بالأسفل ⬇️ لفتحه ومعرفة جائزتك."
        )
        thumbnail_url = recipient.display_avatar.url
    else:
        description = (
            f"**{gifter.mention} أرسل صندوق حظ عام لجميع الأعضاء! 🎉**\n"
            f"أول شخص يضغط على الزر بالأسفل ⬇️ هو من يفوز بالجائزة، سارع قبل غيرك!"
        )
        thumbnail_url = gifter.display_avatar.url

    embed = discord.Embed(title="🎁 صندوق حظ جديد!", description=description, color=discord.Color.gold())
    embed.add_field(name="🎯 نسب الجوائز", value=odds_lines, inline=False)
    if recipient is not None:
        embed.add_field(name="👤 مخصص لـ", value=recipient.mention, inline=True)
    else:
        embed.add_field(name="🌍 النوع", value="صندوق عام (لأي عضو)", inline=True)
    embed.add_field(name="🎁 مُهدى من", value=gifter.mention, inline=True)
    embed.set_thumbnail(url=thumbnail_url)
    embed.set_footer(text=f"{guild.name} • Axion Store", icon_url=guild.icon.url if guild.icon else None)
    embed.timestamp = discord.utils.utcnow()
    return embed


def build_luckybox_result_embed(guild: discord.Guild, gifter: discord.abc.User, winner: discord.abc.User, prize: dict) -> discord.Embed:
    """الإيمبد بعد الفتح: يعرض الجائزة الفائزة فقط."""
    odds_lines = "\n".join(f"• **{p['name']}** — `{p['weight']}%`" for p in LUCKY_BOX_PRIZES)
    embed = discord.Embed(
        title="🎉 تم فتح صندوق الحظ!",
        description=(
            f"{winner.mention} **فتح الصندوق وحصل على:**\n\n"
            f"🏆 **{prize['name']}**"
        ),
        color=discord.Color.gold()
    )
    embed.add_field(name="🎯 نسب الجوائز", value=odds_lines, inline=False)
    embed.add_field(name="🎁 مُهدى من", value=gifter.mention, inline=True)
    embed.set_thumbnail(url=winner.display_avatar.url)
    embed.set_footer(text=f"{guild.name} • Axion Store", icon_url=guild.icon.url if guild.icon else None)
    embed.timestamp = discord.utils.utcnow()
    return embed


class LuckyBoxView(discord.ui.View):
    def __init__(self, gifter: discord.abc.User, recipient: discord.Member = None):
        super().__init__(timeout=None)
        self.gifter = gifter
        self.recipient = recipient  # None يعني صندوق عام يقدر يفتحه أي أحد
        self.opened = False

    @discord.ui.button(label="افتح الصندوق", emoji="🎁", style=discord.ButtonStyle.success, custom_id="open_luckybox_btn")
    async def open_box(self, interaction: discord.Interaction, button: discord.ui.Button):
        # لو الصندوق مخصص لعضو معيّن، لا يفتحه إلا هو
        if self.recipient is not None and interaction.user.id != self.recipient.id:
            await interaction.response.send_message("❌ **هذا الصندوق ليس مخصصاً لك.**", ephemeral=True)
            return

        # هذا الفحص والتعيين بدون أي await بينهما، فهو آمن من التسابق (race condition)
        # حتى لو ضغط أكثر من شخص بنفس اللحظة على صندوق عام.
        if self.opened:
            await interaction.response.send_message("⚠️ **تم فتح هذا الصندوق بالفعل.**", ephemeral=True)
            return
        self.opened = True

        winner = interaction.user
        prize = draw_lucky_box_prize()

        button.disabled = True
        button.label = "تم الفتح ✅"

        # نعطّل الزر على الرسالة الأصلية فقط، والنتيجة نرسلها كرسالة جديدة
        # ظاهرة للجميع في القناة/التذكرة (وليست خاصة بالفاتح فقط).
        await interaction.response.edit_message(view=self)

        result_embed = build_luckybox_result_embed(interaction.guild, self.gifter, winner, prize)
        try:
            await interaction.channel.send(content=winner.mention, embed=result_embed)
        except Exception as e:
            print(f"⚠️ تعذر إرسال نتيجة صندوق الحظ في القناة: {e}")


@bot.command(name="luckybox")
async def luckybox_command(ctx: commands.Context, recipient: discord.Member = None):
    """
    الاستخدام:
    +luckybox <@العضو>  -> صندوق حظ مخصص لهذا العضو فقط
    +luckybox            -> صندوق حظ عام، أول من يضغط الزر يفوز
    """
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = build_luckybox_intro_embed(ctx.guild, ctx.author, recipient)
    view = LuckyBoxView(gifter=ctx.author, recipient=recipient)
    if recipient is not None:
        await ctx.send(content=recipient.mention, embed=embed, view=view)
    else:
        await ctx.send(embed=embed, view=view)


def build_luckybox_catalog_embed(guild: discord.Guild, buyer: discord.Member = None) -> discord.Embed:
    """إيمبد شرح تفصيلي بكل الجوائز المتاحة داخل صندوق الحظ ونسبة كل جائزة."""
    sorted_prizes = sorted(LUCKY_BOX_PRIZES, key=lambda p: p["weight"], reverse=True)
    odds_lines = "\n".join(f"🔹 **{p['name']}** — نسبة الحصول عليها: `{p['weight']}%`" for p in sorted_prizes)

    if buyer is not None:
        description = (
            f"أهلاً بك {buyer.mention} 👋\n\n"
            f"**هذه قائمة كل الجوائز المتاحة داخل صندوق الحظ ونسبة كل واحدة منها:**"
        )
    else:
        description = "**هذه قائمة كل الجوائز المتاحة داخل صندوق الحظ ونسبة كل واحدة منها:**"

    embed = discord.Embed(
        title="🎁 محتويات صندوق الحظ",
        description=description,
        color=discord.Color.gold()
    )
    embed.add_field(name="🎯 الجوائز والنسب", value=odds_lines, inline=False)
    embed.add_field(
        name="ℹ️ ملاحظة",
        value="النسب أعلاه ثابتة ولا تتغير، ويتم اختيار الجائزة بشكل عشوائي بالكامل عند فتح الصندوق.",
        inline=False
    )
    if buyer is not None:
        embed.set_thumbnail(url=buyer.display_avatar.url)
    embed.set_footer(text=f"{guild.name} • Axion Store", icon_url=guild.icon.url if guild.icon else None)
    embed.timestamp = discord.utils.utcnow()
    return embed


@bot.command(name="luckyinfo")
async def luckyinfo_command(ctx: commands.Context, buyer: discord.Member = None):
    """
    الاستخدام:
    +luckyinfo <@المشتري>  -> يرسل شرح مفصل بكل جوائز صندوق الحظ ونسبها، مع منشن المشتري
    +luckyinfo              -> يرسل نفس الشرح بدون تخصيص لأحد
    """
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = build_luckybox_catalog_embed(ctx.guild, buyer)
    if buyer is not None:
        await ctx.send(content=buyer.mention, embed=embed)
    else:
        await ctx.send(embed=embed)


# =========================================================
# ==================== أوامر الـ Say =====================
# =========================================================

@bot.command(name="say")
async def say(ctx: commands.Context, *, message: str = None):
    """
    +say <نص>            -> يرسل نص فقط
    +say (مع إرفاق صورة)  -> يرسل الصورة (مع نص اختياري)
    يدمج هذا الأمر وظيفة +say-photo القديمة.
    """
    try:
        await ctx.message.delete()
    except Exception:
        pass

    files = []
    for attachment in ctx.message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            img_bytes = await attachment.read()
            files.append(discord.File(io.BytesIO(img_bytes), filename=attachment.filename))

    if not message and not files:
        await ctx.reply(
            embed=discord.Embed(description="⚠️ **يجب كتابة رسالة أو إرفاق صورة على الأقل.**", color=discord.Color.orange()),
            mention_author=False, delete_after=6
        )
        return

    await ctx.send(content=message, files=files if files else None)


@bot.command(name="say-embed")
async def say_embed(ctx: commands.Context, *, message: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    await ctx.send(embed=discord.Embed(description=message, color=EMBED_COLOR))


# =========================================================
# =================== نظام البرودكاست ====================
# =========================================================

async def _send_broadcast(ctx: commands.Context, members: list, message: str, label: str):
    status_msg = await ctx.reply(f"⏳ **جاري بدء إرسال {label} لـ {len(members)} عضو...**", mention_author=False)

    sent, failed = 0, 0
    embed = discord.Embed(
        title=f"📢 إعلان رسمي من {ctx.guild.name}",
        description=message,
        color=EMBED_COLOR
    )
    embed.set_footer(text=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

    for member in members:
        if member.bot:
            continue
        try:
            await member.send(embed=embed)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(1)

    await status_msg.edit(
        content=(
            f"✅ **انتهى الإرسال بنجاح!**\n"
            f"• تم الإرسال إلى: **{sent}**\n"
            f"• تعذر الإرسال إلى: **{failed}**"
        )
    )


@bot.command(name="bc")
async def bc_single(ctx: commands.Context, member: discord.Member, *, message: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title=f"📢 رسالة خاصة من إدارة {ctx.guild.name}",
        description=message,
        color=EMBED_COLOR
    )
    embed.set_footer(text=f"بواسطة: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)

    try:
        await member.send(embed=embed)
        await ctx.send(embed=discord.Embed(description=f"✅ **تم إرسال البرودكاست إلى {member.mention} بنجاح.**", color=discord.Color.green()), delete_after=5)
    except discord.Forbidden:
        await ctx.send(embed=discord.Embed(description=f"❌ **تعذر الإرسال لـ {member.mention} (الخاص مقفل).**", color=discord.Color.red()), delete_after=5)


@bot.command(name="bcall")
async def bcall(ctx: commands.Context, *, message: str):
    members = ctx.guild.members

    async def do_bcall(confirm_interaction: discord.Interaction):
        await _send_broadcast(ctx, members, message, "البرودكاست العام")

    await ask_confirmation(
        ctx,
        f"**هل أنت متأكد من إرسال هذه الرسالة لجميع أعضاء السيرفر ({len(members)} عضو)؟**",
        do_bcall,
        author_id=ctx.author.id
    )


@bot.command(name="bc-role")
async def bc_role(ctx: commands.Context, role: discord.Role, *, message: str):
    members = role.members

    async def do_bc_role(confirm_interaction: discord.Interaction):
        await _send_broadcast(ctx, members, message, f"برودكاست رتبة {role.name}")

    await ask_confirmation(
        ctx,
        f"**هل أنت متأكد من إرسال هذه الرسالة لجميع أعضاء رتبة {role.mention} ({len(members)} عضو)؟**",
        do_bc_role,
        author_id=ctx.author.id
    )


@bot.command(name="bc_online")
async def bc_online(ctx: commands.Context, *, message: str):
    members = [m for m in ctx.guild.members if m.status != discord.Status.offline]

    async def do_bc_online(confirm_interaction: discord.Interaction):
        await _send_broadcast(ctx, members, message, "برودكاست المتواجدين أونلاين")

    await ask_confirmation(
        ctx,
        f"**هل أنت متأكد من إرسال هذه الرسالة لجميع المتواجدين أونلاين ({len(members)} عضو)؟**",
        do_bc_online,
        author_id=ctx.author.id
    )


if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على التوكن في ملف .env")
