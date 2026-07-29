import os
import re
import io
import json
import math
import asyncio
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
CONFIG_FILE = "config.json"
CV_LOG_FILE = "cv_log.txt"
SALES_COUNTER_FILE = "sales_counter.json"

# ==== الإعدادات الأساسية ====
DEFAULT_WELCOME_CHANNEL_ID = 1524371159020343318
DEFAULT_REVIEWS_CHANNEL_ID = 1525251733046038528
DEFAULT_TAX_CHANNEL_ID = 1525241937400037567
DEFAULT_BUY_CATEGORY_ID = 1531084521985015868

CUSTOMER_ROLE_ID = 1530380565130514583
BUY_ROLE_ID = 1530380477377024200

ALLOWED_USER_ID = 1426552057984454817
TICKET_NOTIFY_USER_ID = 1426552057984454817

STAR_EMOJI = "⭐"
EMBED_COLOR = discord.Color.from_rgb(47, 49, 54)
TICKET_EMBED_COLOR = discord.Color.blue()

SOLD_WEBHOOK_URL = "https://discord.com/api/webhooks/1532055087625666780/9PFSY6jSK34UmGPDG3GjSZXxJIevTfLYEJ67WJAHT1qygnZYMKsEhcLmIGrD8i1wL-El"

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
# كل قسم = زر مستقل في اللوحة. الحقل "prefix" يُستخدم في اسم
# قناة التذكرة (مثال: fivem-0001) وفي عدّاد التذاكر الخاص به.
TICKET_CATEGORIES = [
    {"key": "robux",     "label": "روبوكس",                          "emoji": "<:Robux:1530419657209548841>",       "prefix": "ROBUX",     "needs_username": True},
    {"key": "fivem",     "label": "فايف ام",                          "emoji": "<:FIVEM:1530421877443530863>",       "prefix": "FIVEM",     "needs_username": False},
    {"key": "credit",    "label": "كريدت",                            "emoji": "<:Pro:1530379178635952200>",         "prefix": "CREDIT",    "needs_username": False},
    {"key": "hypesquad", "label": "هايب سكواد",                       "emoji": "<a:hypesquad:1531633034141630537>",  "prefix": "HYPESQUAD", "needs_username": False},
    {"key": "hosting",   "label": "استضافة",                          "emoji": "<:OX_HOST:1532158984734375986>",     "prefix": "HOST",      "needs_username": False},
    {"key": "snapchat",  "label": "سناب شات",                         "emoji": "<:5378_snapchat:1532159134382686288>", "prefix": "SNAP",    "needs_username": False},
    {"key": "dev",       "label": "برمجة",                            "emoji": "<:dev:1530379905148260542>",         "prefix": "DEV",       "needs_username": False},
    {"key": "windows",   "label": "تفعيل ويندوز",                     "emoji": "<:windows10100:1532163510753165443>", "prefix": "WINDOWS", "needs_username": False},
    {"key": "discord",   "label": "ديسكورد (نيترو / بوستات / افكتات)", "emoji": "<a:AT_Discord:1532164241270902854>", "prefix": "DISCORD",   "needs_username": False},
    {"key": "inquiry",   "label": "استفسار عن منتج",                  "emoji": "❓",                                   "prefix": "INQUIRY",   "needs_username": False},
]
TICKET_PREFIXES = tuple(f"{c['prefix'].lower()}-" for c in TICKET_CATEGORIES)
TICKET_CATEGORY_BY_KEY = {c["key"]: c for c in TICKET_CATEGORIES}

processing_messages = set()
invites_cache = {}

# قنوات تم إشعارها بوضع "غير متوفر" حتى لا يتكرر الإشعار
away_notified_channels = set()


def is_ticket_channel(channel) -> bool:
    return bool(channel and getattr(channel, "name", "").startswith(TICKET_PREFIXES))


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
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
    }


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
if _config_dirty:
    save_config(config)


def get_next_ticket_number(prefix: str) -> int:
    counters = config.setdefault("ticket_counters", {})
    counters[prefix] = counters.get(prefix, 0) + 1
    save_config(config)
    return counters[prefix]


def load_sales_counter():
    if os.path.exists(SALES_COUNTER_FILE):
        try:
            with open(SALES_COUNTER_FILE, "r", encoding="utf-8") as f:
                return int(json.load(f).get("count", 0))
        except Exception:
            pass
    return 0


def save_sales_counter(count: int):
    with open(SALES_COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump({"count": count}, f, ensure_ascii=False, indent=2)


sales_counter = load_sales_counter()


def log_cv_usage(ctx: commands.Context, authorized: bool):
    try:
        timestamp = discord.utils.utcnow().isoformat()
        status = "✅ AUTHORIZED" if authorized else "⛔ DENIED"
        line = (
            f"[{timestamp}] {status} | User: {ctx.author} ({ctx.author.id}) | "
            f"Guild: {ctx.guild.name} ({ctx.guild.id}) | "
            f"Channel: #{ctx.channel.name} ({ctx.channel.id})\n"
        )
        with open(CV_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
        print(f"[+cv] {status} - {ctx.author} ({ctx.author.id}) في #{ctx.channel.name}")
    except Exception as e:
        print(f"خطأ أثناء تسجيل استخدام +cv: {e}")


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
# ==================== كلاسات التذاكر ====================
# =========================================================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق وحذف التذكرة", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description="🔒 **تم إغلاق التذكرة، سيتم حذف القناة تلقائياً خلال 5 ثوانٍ...**",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

        for target, overwrite in interaction.channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot:
                overwrite.send_messages = False
                try:
                    await interaction.channel.set_permissions(target, overwrite=overwrite)
                except Exception:
                    pass

        away_notified_channels.discard(interaction.channel.id)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

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

    # منع فتح أكثر من تذكرة واحدة لنفس العضو (في أي قسم)
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

    ticket_channel = await guild.create_text_channel(
        name=channel_name,
        category=ticket_category,
        overwrites=overwrites
    )

    success_embed = discord.Embed(
        description=f"✅ **تم إنشاء تذكرتك بنجاح!**\n📩 {ticket_channel.mention}",
        color=discord.Color.green()
    )
    if interaction.response.is_done():
        await interaction.followup.send(embed=success_embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=success_embed, ephemeral=True)

    description = (
        f"أهلاً بك {member.mention} في **𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞** 👋\n\n"
        f"📝 يرجى كتابة تفاصيل طلبك بوضوح وسيقوم الطاقم بالرد عليك فوراً.\n"
        f"⏱️ **مدة التسليم المتوقعة:** من **دقيقة واحدة** إلى **48 ساعة** كحد أقصى."
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
    def __init__(self, category: dict):
        super().__init__(
            label=category["label"],
            emoji=category["emoji"],
            style=discord.ButtonStyle.primary,
            custom_id=f"ticket_btn_{category['key']}"
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
        for category in TICKET_CATEGORIES:
            self.add_item(ServiceTicketButton(category))


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
        self.add_view(TicketControlView())

bot = CustomBot()


@bot.check
async def restrict_to_admin(ctx: commands.Context):
    if ctx.guild is None:
        return False
    if ctx.command and ctx.command.name in ("cv", "close", "claim"):
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

    for guild in bot.guilds:
        try:
            invites_cache[guild.id] = await guild.invites()
        except Exception:
            pass


@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    inviter = None

    try:
        old_invites = invites_cache.get(guild.id, [])
        new_invites = await guild.invites()
        invites_cache[guild.id] = new_invites

        for old in old_invites:
            new = discord.utils.get(new_invites, code=old.code)
            if new and new.uses > old.uses:
                inviter = old.inviter
                break
    except Exception:
        pass

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

        await bot.process_commands(message)
    finally:
        processing_messages.discard(message.id)


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
    try:
        invites = await ctx.guild.invites()
        for inv in invites:
            if inv.inviter == target:
                total_uses += inv.uses
    except Exception:
        pass

    embed = discord.Embed(
        title="📊 إحصائية الدعوات",
        description=f"**العضو:** {target.mention}\n**عدد الدعوات:** `{total_uses}` عضو",
        color=EMBED_COLOR
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text=f"{ctx.guild.name} • Invites System", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="close")
async def close_ticket_cmd(ctx: commands.Context):
    if not is_ticket_channel(ctx.channel):
        await ctx.reply(embed=discord.Embed(description="❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", color=discord.Color.red()), mention_author=False)
        return

    await ctx.send(embed=discord.Embed(description="🔒 **تم إغلاق التذكرة. سيتم حذف القناة تلقائياً خلال 5 ثوانٍ...**", color=discord.Color.red()))

    for target, overwrite in ctx.channel.overwrites.items():
        if isinstance(target, discord.Member) and not target.bot:
            overwrite.send_messages = False
            try:
                await ctx.channel.set_permissions(target, overwrite=overwrite)
            except Exception:
                pass

    away_notified_channels.discard(ctx.channel.id)
    await asyncio.sleep(5)
    try:
        await ctx.channel.delete()
    except Exception:
        pass


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
        await ctx.send(embed=discord.Embed(description="🟢 **تم إلغاء وضع الغياب، أنت متوفر الآن.**", color=discord.Color.green()))
        return

    config["away_mode"] = True
    config["away_reason"] = reason.strip() if reason else "غير محدد"
    save_config(config)
    away_notified_channels.clear()

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

    deleted = await ctx.channel.purge(limit=amount)
    msg = await ctx.send(embed=discord.Embed(description=f"🧹 **تم مسح `{len(deleted)}` رسالة بنجاح.**", color=EMBED_COLOR))
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except Exception:
        pass


@bot.command(name="cv")
async def cv_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    if ctx.author.id != ALLOWED_USER_ID:
        log_cv_usage(ctx, authorized=False)
        return

    log_cv_usage(ctx, authorized=True)

    guild = ctx.guild
    channel = ctx.channel

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            send_messages=False, send_messages_in_threads=False,
            create_public_threads=False, create_private_threads=False
        ),
        ctx.author: discord.PermissionOverwrite(
            send_messages=True, send_messages_in_threads=True,
            create_public_threads=True, create_private_threads=True
        ),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
    }

    buy_role = guild.get_role(BUY_ROLE_ID)
    if buy_role:
        overwrites[buy_role] = discord.PermissionOverwrite(
            send_messages=False, send_messages_in_threads=False,
            create_public_threads=False, create_private_threads=False
        )

    try:
        await channel.edit(overwrites=overwrites)
    except Exception as e:
        print(f"خطأ أثناء تعديل صلاحيات القناة عبر +cv: {e}")


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
        description="البريفكس المعتمد: `+` لجميع الأوامر.\n*معظم الأوامر مخصصة لإدارة السيرفر (باستثناء `+cv`, `+close`, `+claim`).*",
        color=EMBED_COLOR,
    )

    embed.add_field(
        name="👑 الأوامر الإدارية العامة",
        value=(
            "`+clear <عدد>` • تنظيف ومسح الرسائل\n"
            "`+lock` / `+unlock` • قفل أو فتح القناة\n"
            "`+cus <@العضو>` • منح رتبة العميل فوراً\n"
            "`+come <@العضو>` • استدعاء عضو إلى القناة\n"
            "`+font <النص>` • زخرفة النصوص بشكل احترافي\n"
            "`+say <الرسالة>` • إرسال نص أو صورة (أو الاثنين) باسم البوت\n"
            "`+say-embed <الرسالة>` • إرسال إيمبد منسق\n"
            "`+find <اسم/آيدي>` • البحث عن عميل داخل السيرفر\n"
            "`+stats` • إحصائيات المتجر والتذاكر\n"
            "`+invites [@عضو]` • عرض عدد دعوات عضو\n"
            "`+away [سبب/off]` • تفعيل أو إلغاء وضع الغياب"
        ),
        inline=False
    )
    embed.add_field(
        name="🛍️ إعدادات المتجر والتذاكر",
        value=(
            "`+panel` • إرسال لوحة فتح التذاكر (كل الأقسام)\n"
            "`+claim` • استلام التذكرة الحالية\n"
            "`+close` • إغلاق التذكرة الحالية\n"
            "`+kl` • تحذير بالإغلاق التلقائي\n"
            "`+addto <@عضو>` • إضافة عضو للتذكرة الحالية\n"
            "`+removeto <@عضو>` • إزالة عضو من التذكرة الحالية\n"
            "`+terms` • عرض قوانين المتجر\n"
            "`+bnm <ID>` • تعيين كاتيجوري التذاكر\n"
            "`+setpay` • إعداد وتحديث طرق الدفع\n"
            "`+pay` • عرض طرق الدفع الحالية\n"
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
            "`+sold \"المنتج\" <@المشتري>` • تسجيل عملية بيع وإرسالها لقناة المبيعات\n"
            "(ضع اسم المنتج بين علامتي اقتباس إن كان يحتوي على أكثر من كلمة)"
        ),
        inline=False
    )
    embed.add_field(
        name="📢 البرودكاست",
        value=(
            "`+bc <@العضو> <الرسالة>` • رسالة خاصة لشخص واحد\n"
            "`+bcall <الرسالة>` • رسالة خاصة للجميع\n"
            "`+bc-role <@الرتبة> <الرسالة>` • رسالة خاصة لرتبة محددة\n"
            "`+bc_online <الرسالة>` • رسالة للمتواجدين أونلاين"
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
        description="**يرجى اختيار طريقة الدفع المناسبة وتحويل المبلغ المطلوب:**",
        color=EMBED_COLOR
    )
    embed.add_field(name="📱 ليبيانا", value=f"`{payments.get('ليبيانا', 'لايوجد')}`", inline=False)
    embed.add_field(name="📱 مدار", value=f"`{payments.get('مدار', 'لايوجد')}`", inline=False)
    embed.add_field(name="🟡 بايننس", value=f"`{payments.get('بايننس', 'لايوجد')}`", inline=False)
    embed.add_field(name="🏛️ LTC", value=f"`{payments.get('LTC', 'لايوجد')}`", inline=False)
    embed.add_field(name="💳 كريديت", value=f"`{payments.get('كريديت', 'لايوجد')}`", inline=False)
    embed.set_footer(text="يرجى إرسال صورة الإثبات داخل التذكرة بعد التحويل.")

    await ctx.send(embed=embed)


@bot.command(name="panel")
async def panel_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    categories_lines = "\n".join(f"{cat['emoji']} **{cat['label']}**" for cat in TICKET_CATEGORIES)

    embed = discord.Embed(
        title="🎫 مركز الطلبات والاستفسارات - 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞",
        description=(
            "لو حاب تستفسر عن اي شيء يخص المتجر او يخص منتج يمكنك الضغط على زر **استفسار عن منتج** ⬇️\n\n"
            f"{categories_lines}\n\n"
            "📝 اضغط على الزر المناسب لطلبك وسيتم فتح تذكرة خاصة بك فوراً.\n"
            "⚠️ *ملاحظة: يحق لك فتح تذكرة واحدة فقط في نفس الوقت.*"
        ),
        color=TICKET_EMBED_COLOR
    )
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text="Axion Store • DEV BY : @D0JW")

    await ctx.send(embed=embed, view=TicketSetupView())


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

        self.rate_view.rate_button.disabled = True
        self.rate_view.rate_button.label = "تم التقييم بنجاح ✅"
        await interaction.message.edit(view=self.rate_view)


class RateView(discord.ui.View):
    def __init__(self, seller: discord.Member, buyer: discord.Member, product: str):
        super().__init__(timeout=None)
        self.seller = seller
        self.buyer = buyer
        self.product = product

    @discord.ui.button(label="اضغط لتقييم الخدمة", style=discord.ButtonStyle.success, emoji="⭐")
    async def rate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer.id:
            await interaction.response.send_message("❌ **هذا التقييم مخصص للمشتري فقط.**", ephemeral=True)
            return
        await interaction.response.send_modal(RateModal(self.seller, self.buyer, self.product, self))


@bot.command(name="rate")
async def rate_prefix(ctx: commands.Context, buyer: discord.Member, *, product: str):
    view = RateView(seller=ctx.author, buyer=buyer, product=product)

    embed = discord.Embed(
        description=f"{buyer.mention} 👋 **شكراً لثقتك بنا!**\nنتمنى منك مشاركة رأيك وتقييم الخدمة عبر الزر أدناه.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed, view=view)


# =========================================================
# =================== نظام تسجيل المبيعات: +sold ===================
# =========================================================

@bot.command(name="sold")
async def sold_command(ctx: commands.Context, product: str, buyer: discord.Member):
    """
    الاستخدام: +sold "اسم المنتج" @المشتري
    (استخدم علامتي اقتباس حول اسم المنتج إذا كان يحتوي على أكثر من كلمة)
    """
    global sales_counter

    try:
        await ctx.message.delete()
    except Exception:
        pass

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

    sent_ok = True
    try:
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(SOLD_WEBHOOK_URL, session=session)
            await webhook.send(
                embed=embed,
                username="Axion Store | Sales",
                avatar_url=ctx.guild.icon.url if ctx.guild.icon else None
            )
    except Exception as e:
        sent_ok = False
        print(f"خطأ أثناء إرسال ويبهوك عملية البيع: {e}")

    if sent_ok:
        await ctx.send(embed=discord.Embed(description=f"✅ **تم تسجيل عملية البيع بنجاح، رقم العملية:** `{order_number}`", color=discord.Color.green()))
    else:
        await ctx.send(embed=discord.Embed(description=f"⚠️ **تم تسجيل عملية البيع رقم `{order_number}` محلياً، لكن تعذر إرسالها عبر الويبهوك.**", color=discord.Color.orange()))


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
    await _send_broadcast(ctx, ctx.guild.members, message, "البرودكاست العام")


@bot.command(name="bc-role")
async def bc_role(ctx: commands.Context, role: discord.Role, *, message: str):
    await _send_broadcast(ctx, role.members, message, f"برودكاست رتبة {role.name}")


@bot.command(name="bc_online")
async def bc_online(ctx: commands.Context, *, message: str):
    members = [m for m in ctx.guild.members if m.status != discord.Status.offline]
    await _send_broadcast(ctx, members, message, "برودكاست المتواجدين أونلاين")


if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على التوكن في ملف .env")
