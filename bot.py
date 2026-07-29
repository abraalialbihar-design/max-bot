import os
import re
import io
import json
import math
import random
import asyncio
import hashlib
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
CONFIG_FILE = "config.json"
CV_LOG_FILE = "cv_log.txt"
INVITE_LOG_FILE = "invite_log.json"

# ==== الإعدادات الأساسية ====
DEFAULT_WELCOME_CHANNEL_ID = 1526255263462461530
DEFAULT_REVIEWS_CHANNEL_ID = 1513286580456919151
CUSTOMER_ROLE_ID = 1530380565130514583

# ==== أيديات رتب التذاكر ====
BUY_ROLE_ID = 1530380477377024200      # رتبة الشراء
SUPPORT_ROLE_ID = 1530413725578694746  # رتبة الدعم الفني

# ==== آيدي الشخص المسموح له بـ +cv ====
ALLOWED_USER_ID = 1426552057984454817

# ==== آيدي الشخص اللي يستلم إشعار خاص عند فتح أي تذكرة ====
TICKET_NOTIFY_USER_ID = 1426552057984454817

STAR_EMOJI = "⭐"
EMBED_COLOR = discord.Color.from_rgb(47, 49, 54)

DEFAULT_PAYMENT_METHODS = {
    "مدار": "لايوجد",
    "ليبيانا": "لايوجد",
    "بايننس": "لايوجد",
    "LTC": "لايوجد",
    "كريديت": "لايوجد"
}

# قوانين متجر Axion Store (مصدر واحد فقط، لا يُخزَّن في config لتفادي التعارض)
AXION_TERMS = (
    "📋 **قوانين متجر 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞**\n\n"
    "1️⃣ **1 -** يمنع طلب استبدال السلعة او استرداد الاموال بعد شرائك شي من المتجر ويجب أن تكون متأكدا قبل شرائك.\n\n"
    "2️⃣ **2 -** لا يحق للعميل طلب تخفيض سعر او شيء مجاني من المتجر.\n\n"
    "3️⃣ **3 -** يحق للعميل شراء هدية لشخص من منتجات المتجر.\n\n"
    "4️⃣ **4 -** جميع المشتريات تكون من خلال التذاكر المخصصة للمتجر فقط لا غير."
)

processing_messages = set()
invites_cache = {}


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
        "tax_channel_id": None,
        "buy_category_id": None,
        "support_category_id": None,
        "payment_methods": DEFAULT_PAYMENT_METHODS
    }


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


config = load_config()
_config_dirty = False
if "payment_methods" not in config:
    config["payment_methods"] = DEFAULT_PAYMENT_METHODS
    _config_dirty = True
if _config_dirty:
    save_config(config)


def load_invite_log():
    if os.path.exists(INVITE_LOG_FILE):
        try:
            with open(INVITE_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_invite_log(data):
    with open(INVITE_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


invite_log = load_invite_log()   # member_id (str) -> {"inviter_id","inviter_name","invited_at"}


def log_cv_usage(ctx: commands.Context, authorized: bool):
    """يسجل كل استخدام لأمر +cv (ناجح أو مرفوض) في ملف لوج دائم."""
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


# ---------- دالة استخراج وتحويل المبالغ والأوقات ----------
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
        await interaction.response.send_message("🔒 **تم إغلاق التذكرة. سيتم حذف القناة تلقائياً خلال 5 ثوانٍ...**")

        for target, overwrite in interaction.channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot:
                overwrite.send_messages = False
                try:
                    await interaction.channel.set_permissions(target, overwrite=overwrite)
                except Exception:
                    pass

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except Exception:
            pass

    @discord.ui.button(label="استلام التذكرة (Claim)", emoji="🙋‍♂️", style=discord.ButtonStyle.secondary, custom_id="claim_ticket_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            description=f"✅ **تم استلام التذكرة بواسطة:** {interaction.user.mention}\nسيقوم بمتابعة طلبك الآن.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


class TicketSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _create_ticket_channel(self, interaction: discord.Interaction, prefix: str, title_msg: str, role_id: int, category_key: str):
        guild = interaction.guild
        member = interaction.user

        # 🔒 شرط فتح تذكرة واحدة فقط لكل عضو (أي نوع - شراء أو دعم)
        for channel in guild.text_channels:
            if channel.name.startswith(("buy-", "support-")):
                overwrite = channel.overwrites_for(member)
                if overwrite.view_channel:
                    await interaction.response.send_message(
                        f"⚠️ **لديك تذكرة مفتوحة بالفعل!** {channel.mention}\nيمكنك فتح تذكرة واحدة فقط في نفس الوقت.",
                        ephemeral=True
                    )
                    return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        for role in guild.roles:
            if role.permissions.administrator or role.id in (BUY_ROLE_ID, SUPPORT_ROLE_ID):
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        cat_id = config.get(category_key)
        category = guild.get_channel(cat_id) if cat_id else None

        if not category:
            category = discord.utils.get(guild.categories, name="TICKETS")
            if not category:
                try:
                    category = await guild.create_category("TICKETS")
                except Exception:
                    category = None

        ticket_channel = await guild.create_text_channel(
            name=f"{prefix}-{member.name[:8]}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"✅ **تم إنشاء التذكرة بنجاح!** {ticket_channel.mention}", ephemeral=True)

        embed = discord.Embed(
            title=title_msg,
            description=(
                f"أهلاً بك {member.mention} في **𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞** 👋\n"
                f"يرجى كتابة تفاصيل طلبك بوضوح وسيقوم الطاقم بالرد عليك فوراً.\n\n"
                f"⏱️ **مدة التسليم المتوقعة:** من **دقيقة واحدة** إلى **48 ساعة** كحد أقصى."
            ),
            color=EMBED_COLOR
        )
        embed.set_footer(text=f"{guild.name} • Axion Store", icon_url=guild.icon.url if guild.icon else None)

        mention_content = f"{member.mention} <@&{role_id}>"
        await ticket_channel.send(content=mention_content, embed=embed, view=TicketControlView())

        # ---- إشعار خاص لصاحب الآيدي المحدد عند فتح أي تذكرة ----
        try:
            notify_user = guild.get_member(TICKET_NOTIFY_USER_ID) or await guild.fetch_member(TICKET_NOTIFY_USER_ID)
        except Exception:
            notify_user = None

        if notify_user:
            notify_embed = discord.Embed(
                title="🎫 تم فتح تذكرة جديدة",
                description=(
                    f"👤 **العضو:** {member.mention} (`{member.id}`)\n"
                    f"📌 **النوع:** {title_msg}\n"
                    f"💬 **القناة:** {ticket_channel.mention}\n"
                    f"🏠 **السيرفر:** {guild.name}"
                ),
                color=EMBED_COLOR
            )
            notify_embed.timestamp = discord.utils.utcnow()
            try:
                await notify_user.send(embed=notify_embed)
            except Exception:
                pass

    @discord.ui.button(label="شراء منتج", emoji="🛒", style=discord.ButtonStyle.success, custom_id="persistent_buy_ticket")
    async def buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket_channel(interaction, "buy", "🛒 تذكرة شراء منتج - Axion Store", BUY_ROLE_ID, "buy_category_id")

    @discord.ui.button(label="الدعم الفنى", emoji="🛠️", style=discord.ButtonStyle.primary, custom_id="persistent_support_ticket")
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket_channel(interaction, "support", "🛠️ تذكرة الدعم الفني - Axion Store", SUPPORT_ROLE_ID, "support_category_id")


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


# ---------- تقييد استخدام الأوامر لمن يملك Administrator (باستثناء أوامر التذاكر الأساسية) ----------
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
        await ctx.reply("❌ **عذراً، هذا الأمر مخصص فقط لإدارة السيرفر.**", mention_author=False)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("⚠️ **الرجاء كتابة المعطى المطلوب بشكل صحيح.**", mention_author=False)
    elif isinstance(error, commands.BadArgument):
        await ctx.reply("⚠️ **تأكد من صحة البيانات أو المنشن المدخل.**", mention_author=False)
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

    if not check_inactive_tickets.is_running():
        check_inactive_tickets.start()


# ---------- نظام الترحيب (مع تتبع الداعي) ----------
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

    # تسجيل بيانات الدعوة بشكل دائم عشان أوامر +winv و +invites
    invite_log[str(member.id)] = {
        "inviter_id": inviter.id if inviter else None,
        "inviter_name": str(inviter) if inviter else None,
        "invited_at": discord.utils.utcnow().isoformat()
    }
    save_invite_log(invite_log)

    channel_id = config.get("welcome_channel_id", DEFAULT_WELCOME_CHANNEL_ID)
    channel = guild.get_channel(channel_id)
    if channel is None:
        return

    inv_text = f"\n📩 **تم الدعوة بواسطة:** {inviter.mention}" if inviter else "\n📩 **تم الدعوة بواسطة:** غير معروف"
    embed = discord.Embed(
        title="✨ أهلاً بك في 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞 ✨",
        description=f"مرحباً بك {member.mention} في **{guild.name}** 🌸{inv_text}",
        color=EMBED_COLOR
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="📊 الترتيب", value=f"**#{guild.member_count}**", inline=True)
    embed.add_field(name="📅 إنشاء الحساب", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
    embed.set_footer(text=f"{guild.name} • Welcome", icon_url=guild.icon.url if guild.icon else None)
    embed.timestamp = discord.utils.utcnow()

    await channel.send(content=f"🎉 {member.mention}", embed=embed)


# ---------- الرد التلقائي + حساب الضريبة ----------
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
                await message.reply(f"💳 **المبلغ مع الضريبة:** `{total_with_tax:,}`", mention_author=False)

        await bot.process_commands(message)
    finally:
        processing_messages.discard(message.id)


# =========================================================
# ==================== الأوامر الكاملة =====================
# =========================================================

# ---------- 🔒 +lock / 🔓 +unlock ----------
@bot.command(name="lock")
async def lock_channel(ctx: commands.Context):
    try: await ctx.message.delete()
    except Exception: pass
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 **تم قفل القناة بنجاح.**")


@bot.command(name="unlock")
async def unlock_channel(ctx: commands.Context):
    try: await ctx.message.delete()
    except Exception: pass
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 **تم فتح القناة بنجاح.**")


# ---------- ⏱️ مؤقت استلام التسليم (Delivery Timer) ----------
@bot.command(name="timer")
async def delivery_timer(ctx: commands.Context, hours: int = 24):
    if hours < 1 or hours > 48:
        await ctx.reply("⚠️ **المدة المتاحة لتسليم الطلب هي من 1 ساعة إلى 48 ساعة.**", mention_author=False)
        return

    try: await ctx.message.delete()
    except Exception: pass

    embed = discord.Embed(
        title="⏱️ مؤقت تسليم الطلب (Delivery Timer)",
        description=(
            f"تم بدء عداد تسليم الطلب للعميل.\n\n"
            f"⏳ **المدة المحددة:** `{hours}` ساعة"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞 • نلتزم بالتسليم في الوقت المحدد من دقيقة إلى 48 ساعة.")
    await ctx.send(embed=embed)


# ---------- 📜 قوانين المتجر (+terms) ----------
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


# ---------- 🙋‍♂️ استلام التذكرة (+claim) ----------
@bot.command(name="claim")
async def claim_cmd(ctx: commands.Context):
    if not ctx.channel.name.startswith(("buy-", "support-")):
        await ctx.reply("❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", mention_author=False)
        return

    try: await ctx.message.delete()
    except Exception: pass

    embed = discord.Embed(
        description=f"✅ **تم استلام التذكرة بواسطة:** {ctx.author.mention}\nسيقوم بمتابعة طلبك الآن.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


# ---------- ➕ إضافة/إزالة عضو من التذكرة (+addto / +removeto) ----------
@bot.command(name="addto")
async def addto_command(ctx: commands.Context, member: discord.Member):
    if not ctx.channel.name.startswith(("buy-", "support-")):
        await ctx.reply("❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", mention_author=False)
        return

    try: await ctx.message.delete()
    except Exception: pass

    try:
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
    except Exception as e:
        await ctx.send(f"❌ **تعذر إضافة العضو:** {e}")
        return

    embed = discord.Embed(
        description=f"✅ **تم إضافة {member.mention} إلى هذه التذكرة.**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.command(name="removeto")
async def removeto_command(ctx: commands.Context, member: discord.Member):
    if not ctx.channel.name.startswith(("buy-", "support-")):
        await ctx.reply("❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", mention_author=False)
        return

    try: await ctx.message.delete()
    except Exception: pass

    try:
        await ctx.channel.set_permissions(member, overwrite=None)
    except Exception as e:
        await ctx.send(f"❌ **تعذر إزالة العضو:** {e}")
        return

    embed = discord.Embed(
        description=f"🚫 **تمت إزالة {member.mention} من هذه التذكرة.**",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)


# ---------- 📊 فحص الدعوات (+invites) ----------
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

    invited_ids = [
        mid for mid, data in invite_log.items()
        if data.get("inviter_id") == target.id
    ]

    embed = discord.Embed(
        description=f"📊 **عدد دعوات {target.mention}:** `{total_uses}` عضو",
        color=EMBED_COLOR
    )

    if invited_ids:
        mentions_list = "\n".join(f"<@{mid}>" for mid in invited_ids[:25])
        if len(invited_ids) > 25:
            mentions_list += f"\n... و`{len(invited_ids) - 25}` عضو آخر"
        embed.add_field(
            name=f"👥 الأعضاء الذين دخلوا عن طريقه ({len(invited_ids)})",
            value=mentions_list,
            inline=False
        )
    else:
        embed.add_field(name="👥 الأعضاء الذين دخلوا عن طريقه", value="لا يوجد", inline=False)

    await ctx.reply(embed=embed, mention_author=False)


# ---------- 🔎 مين دعا هذا الشخص (+winv) ----------
@bot.command(name="winv")
async def who_invited(ctx: commands.Context, *, target: str):
    target = target.strip()
    match = re.match(r"^<@!?(\d+)>$", target)
    if match:
        target_id = int(match.group(1))
    else:
        try:
            target_id = int(target)
        except ValueError:
            await ctx.reply("⚠️ **الرجاء إدخال منشن صحيح أو آيدي حساب.**", mention_author=False)
            return

    entry = invite_log.get(str(target_id))
    if not entry or not entry.get("inviter_id"):
        await ctx.reply(f"⚠️ **لا توجد بيانات دعوة مسجلة لهذا العضو (`{target_id}`).**", mention_author=False)
        return

    inviter_id = entry["inviter_id"]
    inviter_name = entry.get("inviter_name") or "غير معروف"

    embed = discord.Embed(
        description=(
            f"👤 **العضو:** <@{target_id}> (`{target_id}`)\n"
            f"📩 **دخل عن طريق:** {inviter_name} (<@{inviter_id}>)"
        ),
        color=EMBED_COLOR
    )
    await ctx.reply(embed=embed, mention_author=False)


# ---------- 🔒 إغلاق التذكرة (+close) ----------
@bot.command(name="close")
async def close_ticket_cmd(ctx: commands.Context):
    if not ctx.channel.name.startswith(("buy-", "support-")):
        await ctx.reply("❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", mention_author=False)
        return

    await ctx.send("🔒 **تم إغلاق التذكرة. سيتم حذف القناة تلقائياً خلال 5 ثوانٍ...**")

    for target, overwrite in ctx.channel.overwrites.items():
        if isinstance(target, discord.Member) and not target.bot:
            overwrite.send_messages = False
            try:
                await ctx.channel.set_permissions(target, overwrite=overwrite)
            except Exception:
                pass

    await asyncio.sleep(5)
    try:
        await ctx.channel.delete()
    except Exception:
        pass


# ---------- ⚠️ تحذير قبل الإغلاق (+kl) - رسالة فقط بدون أي إجراء تلقائي ----------
@bot.command(name="kl")
async def kl_warning(ctx: commands.Context):
    if not ctx.channel.name.startswith(("buy-", "support-")):
        await ctx.reply("❌ **هذا الأمر يستخدم فقط داخل قنوات التذاكر.**", mention_author=False)
        return

    try:
        await ctx.message.delete()
    except Exception:
        pass

    await ctx.send(
        "<a:OWNER:1530380061595795526>**في حالة لم يكن هناك رد لمده تتراوح ما بين 30 إلى 60 دقيقة ، سيتم اغلاق التذكره**"
    )

@bot.command(name="bnm")
async def set_buy_category(ctx: commands.Context, category_id: int):
    category = ctx.guild.get_channel(category_id)
    if category is None or not isinstance(category, discord.CategoryChannel):
        await ctx.reply("❌ **لم يتم العثور على الكاتيجوري (Category) المحددة.**", mention_author=False)
        return

    config["buy_category_id"] = category.id
    save_config(config)
    await ctx.reply(f"✅ **تم اعتماد الكاتيجوري `{category.name}` لتذاكر الشراء.**", mention_author=False)


@bot.command(name="dfg")
async def set_support_category(ctx: commands.Context, category_id: int):
    category = ctx.guild.get_channel(category_id)
    if category is None or not isinstance(category, discord.CategoryChannel):
        await ctx.reply("❌ **لم يتم العثور على الكاتيجوري (Category) المحددة.**", mention_author=False)
        return

    config["support_category_id"] = category.id
    save_config(config)
    await ctx.reply(f"✅ **تم اعتماد الكاتيجوري `{category.name}` لتذاكر الدعم الفني.**", mention_author=False)


# =========================================================
# ================= ⚡ الإعداد السريع (+sal) ================
# =========================================================

@bot.command(name="sal")
async def sal_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    results = []

    buy_cat = ctx.guild.get_channel(1531084521985015868)
    if buy_cat and isinstance(buy_cat, discord.CategoryChannel):
        config["buy_category_id"] = buy_cat.id
        results.append(f"✅ **كاتيجوري الشراء →** `{buy_cat.name}`")
    else:
        results.append("❌ **لم يتم العثور على كاتيجوري الشراء (تأكد من الآيدي).**")

    support_cat = ctx.guild.get_channel(1531084999770509463)
    if support_cat and isinstance(support_cat, discord.CategoryChannel):
        config["support_category_id"] = support_cat.id
        results.append(f"✅ **كاتيجوري الدعم الفني →** `{support_cat.name}`")
    else:
        results.append("❌ **لم يتم العثور على كاتيجوري الدعم الفني (تأكد من الآيدي).**")

    welcome_ch = ctx.guild.get_channel(1524371159020343318)
    if welcome_ch:
        config["welcome_channel_id"] = welcome_ch.id
        results.append(f"✅ **قناة الترحيب →** {welcome_ch.mention}")
    else:
        results.append("❌ **لم يتم العثور على قناة الترحيب (تأكد من الآيدي).**")

    reviews_ch = ctx.guild.get_channel(1525251733046038528)
    if reviews_ch:
        config["reviews_channel_id"] = reviews_ch.id
        results.append(f"✅ **قناة التقييمات →** {reviews_ch.mention}")
    else:
        results.append("❌ **لم يتم العثور على قناة التقييمات (تأكد من الآيدي).**")

    tax_ch = ctx.guild.get_channel(1525241937400037567)
    if tax_ch:
        config["tax_channel_id"] = tax_ch.id
        results.append(f"✅ **قناة حساب الضريبة →** {tax_ch.mention}")
    else:
        results.append("❌ **لم يتم العثور على قناة الضريبة (تأكد من الآيدي).**")

    save_config(config)

    embed = discord.Embed(
        title="⚡ تم تنفيذ الإعداد السريع",
        description="\n".join(results),
        color=EMBED_COLOR
    )
    embed.set_footer(text=f"{ctx.guild.name} • Quick Setup")
    await ctx.send(embed=embed)


@tasks.loop(hours=1)
async def check_inactive_tickets():
    now = discord.utils.utcnow()
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name.startswith(("buy-", "support-")):
                try:
                    history = [m async for m in channel.history(limit=1)]
                    if not history:
                        continue

                    last_msg = history[0]
                    if (now - last_msg.created_at).total_seconds() >= 86400:
                        ticket_owner = None
                        for target in channel.overwrites:
                            if isinstance(target, discord.Member) and not target.bot:
                                ticket_owner = target
                                break

                        if ticket_owner:
                            embed = discord.Embed(
                                title="⌛ **تذكير بتذكرة خاملة**",
                                description=(
                                    f"مرحباً {ticket_owner.mention} 👋\n\n"
                                    f"لاحظنا عدم وجود أي تفاعل في التذكرة منذ 24 ساعة.\n"
                                    f"يرجى توضيح طلبك أو الرد للربط مع فريق الدعم والإدارة."
                                ),
                                color=discord.Color.orange()
                            )
                            embed.set_footer(text=f"{guild.name} • Auto Reminder System")
                            await channel.send(content=f"🔔 {ticket_owner.mention}", embed=embed)
                except Exception as e:
                    print(f"خطأ أثناء فحص التذكرة {channel.name}: {e}")


# =========================================================
# ===================== أمر Clear (+clear) ================
# =========================================================

@bot.command(name="clear")
async def clear_messages(ctx: commands.Context, amount: int = 100):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    deleted = await ctx.channel.purge(limit=amount)
    msg = await ctx.send(f"🧹 **تم مسح `{len(deleted)}` رسالة بنجاح.**")
    await asyncio.sleep(3)
    try:
        await msg.delete()
    except Exception:
        pass


# =========================================================
# ===================== أمر CV ======================
# =========================================================

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
            send_messages=False,
            send_messages_in_threads=False,
            create_public_threads=False,
            create_private_threads=False
        ),
        ctx.author: discord.PermissionOverwrite(
            send_messages=True,
            send_messages_in_threads=True,
            create_public_threads=True,
            create_private_threads=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True
        )
    }

    buy_role = guild.get_role(BUY_ROLE_ID)
    if buy_role:
        overwrites[buy_role] = discord.PermissionOverwrite(
            send_messages=False,
            send_messages_in_threads=False,
            create_public_threads=False,
            create_private_threads=False
        )

    support_role = guild.get_role(SUPPORT_ROLE_ID)
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(
            send_messages=False,
            send_messages_in_threads=False,
            create_public_threads=False,
            create_private_threads=False
        )

    try:
        await channel.edit(overwrites=overwrites)
    except Exception as e:
        print(f"خطأ أثناء تعديل صلاحيات القناة عبر +cv: {e}")


# =========================================================
# ==================== أمر إعطاء رتبة العميل (+cus) ====================
# =========================================================

@bot.command(name="cus")
async def give_customer_role(ctx: commands.Context, member: discord.Member):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    role = ctx.guild.get_role(CUSTOMER_ROLE_ID)
    if role is None:
        await ctx.send("❌ **لم يتم العثور على رتبة العميل في السيرفر.**")
        return

    if role in member.roles:
        await ctx.send(f"⚠️ {member.mention} **يمتلك الرتبة بالفعل!**")
        return

    try:
        await member.add_roles(role)
        embed = discord.Embed(
            description=f"✨ **تم منح رتبة {role.mention} إلى {member.mention} بنجاح!** 🎉",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ **البوت لا يملك صلاحية لإعطاء هذه الرتبة.**")
    except Exception as e:
        await ctx.send(f"❌ **حدث خطأ:** {e}")


# =========================================================
# ========================  +help  ========================
# =========================================================

@bot.command(name="help")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="⚙️ لوحة الأوامر والتحكم الكاملة",
        description="البريفكس المعتمد: `+`\n*معظم الأوامر مخصصة لإدارة السيرفر (باستثناء `+cv`, `+close`, `+claim`).*",
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
            "`+say <الرسالة>` • إرسال نص باسم البوت\n"
            "`+say-embed <الرسالة>` • إرسال إيمبد منسق\n"
            "`+say-photo <الرسالة>` • إرسال صورة مرفقة مع نص باسم البوت\n"
            "`+invites [@عضو]` • عرض عدد دعوات عضو والأعضاء اللي دخلوا عن طريقه\n"
            "`+winv <منشن/آيدي>` • معرفة مين دعا عضو معين"
        ),
        inline=False
    )
    embed.add_field(
        name="🛍️ إعدادات المتجر والتذاكر",
        value=(
            "`+panel` • إرسال لوحة فتح التذاكر\n"
            "`+claim` • استلام التذكرة الحالية\n"
            "`+close` • إغلاق التذكرة الحالية\n"
            "`+kl` • تحذير بالإغلاق التلقائي بعد 30-60 دقيقة بدون رد\n"
            "`+addto <@عضو>` • إضافة عضو للتذكرة الحالية\n"
            "`+removeto <@عضو>` • إزالة عضو من التذكرة الحالية\n"
            "`+timer <ساعات>` • بدء مؤقت تسليم الطلب\n"
            "`+terms` • عرض قوانين المتجر\n"
            "`+bnm <ID>` • تعيين كاتيجوري تذاكر الشراء\n"
            "`+dfg <ID>` • تعيين كاتيجوري تذاكر الدعم الفني\n"
            "`+setpay` • إعداد وتحديث طرق الدفع\n"
            "`+pay` • عرض طرق الدفع الحالية\n"
            "`+tax [ID]` • تعيين روم حساب الضريبة (الحالية أو بالآيدي)\n"
            "`+rate <@المشتري> <المنتج>` • طلب تقييم من المشتري\n"
            "`+rate-setup <ID>` • تعيين روم التقييمات\n"
            "`+setup-welcome <ID>` • تعيين روم الترحيب"
        ),
        inline=False
    )
    embed.add_field(
        name="📢 البرودكاست والإعلانات",
        value=(
            "`+bc <@العضو> <الرسالة>` • إرسال برودكاست لشخص واحد\n"
            "`+bcall <الرسالة>` • إرسال خاص للجميع\n"
            "`+bc-role <@الرتبة> <الرسالة>` • إرسال خاص لرتبة محددة\n"
            "`+bc_online <الرسالة>` • إرسال للمتواجدين أونلاين"
        ),
        inline=False
    )
    embed.set_footer(text=f"{ctx.guild.name} • Control Panel", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.reply(embed=embed, mention_author=False)


# ---------- +tax (tax id room) ----------
@bot.command(name="tax", aliases=["tax-setup"])
async def tax_setup(ctx: commands.Context, room_id: int = None):
    channel = ctx.guild.get_channel(room_id) if room_id else ctx.channel
    if channel is None:
        await ctx.reply("❌ **لم يتم العثور على القناة المحددة.**", mention_author=False)
        return

    config["tax_channel_id"] = channel.id
    save_config(config)
    await ctx.reply(f"✅ **تم اعتماد قناة {channel.mention} لحساب الضريبة تلقائياً.**", mention_author=False)


# ---------- +ping ----------
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    await ctx.reply(f"⚡ **سرعة الاستجابة:** `{latency}ms`", mention_author=False)


# ---------- +serverinfo ----------
@bot.command(name="serverinfo")
async def serverinfo(ctx: commands.Context):
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 معلومات السيرفر: {guild.name}", color=EMBED_COLOR)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👥 الأعضاء", value=f"**{guild.member_count}**", inline=True)
    embed.add_field(name="👑 المالك", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="📅 تاريخ الإنشاء", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
    await ctx.reply(embed=embed, mention_author=False)


# ---------- +font ----------
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


# ---------- +come ----------
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
        await ctx.reply(f"✅ **تم إرسال الإشعار بنجاح إلى {member.mention}**", mention_author=False)
    except discord.Forbidden:
        await ctx.reply(f"❌ **تعذر الإرسال لـ {member.mention} (الخاص مقفل).**", mention_author=False)


# ---------- +setup-welcome ----------
@bot.command(name="setup-welcome")
async def setup_welcome(ctx: commands.Context, channel_id: int):
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.reply("❌ **لم يتم العثور على القناة المحددة.**", mention_author=False)
        return

    config["welcome_channel_id"] = channel.id
    save_config(config)
    await ctx.reply(f"✅ **تم حفظ {channel.mention} كقناة رسمية للترحيب.**", mention_author=False)


# ---------- +rate-setup ----------
@bot.command(name="rate-setup")
async def rate_setup(ctx: commands.Context, channel_id: int):
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.reply("❌ **لم يتم العثور على القناة المحددة.**", mention_author=False)
        return

    config["reviews_channel_id"] = channel.id
    save_config(config)
    await ctx.reply(f"✅ **تم حفظ {channel.mention} كقناة رسمية للتقييمات.**", mention_author=False)


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
    await ctx.send("⚙️ **اضغط على الزر لتعديل بيانات طرق الدفع الخاصة بالمتجر:**", view=view)


@bot.command(name="pay")
async def pay_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    payments = config.get("payment_methods", DEFAULT_PAYMENT_METHODS)

    embed = discord.Embed(
        title="💳 طرق الدفع المعتمدة",
        description="**يرجى اختيار طريقة الدفع المناسبة وتحويل المبلغ المطلوبة:**",
        color=EMBED_COLOR
    )

    embed.add_field(name="📱 ليبيانا", value=f"`{payments.get('ليبيانا', 'لايوجد')}`", inline=False)
    embed.add_field(name="📱 مدار", value=f"`{payments.get('مدار', 'لايوجد')}`", inline=False)
    embed.add_field(name="🟡 بايننس", value=f"`{payments.get('بايننس', 'لايوجد')}`", inline=False)
    embed.add_field(name="🏛️ LTC", value=f"`{payments.get('LTC', 'لايوجد')}`", inline=False)
    embed.add_field(name="💳 كريديت", value=f"`{payments.get('كريديت', 'لايوجد')}`", inline=False)
    embed.set_footer(text="يرجى إرسال صورة الإثبات داخل التذكرة بعد التحويل.")

    await ctx.send(embed=embed)


# =========================================================
# ================= لوحة التذاكر (+panel) ==================
# =========================================================

@bot.command(name="panel")
async def panel_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title="🎫 مركز الشراء والدعم الفني - 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞",
        description=(
            "يرجى الضغط على الزر المناسب لفتح تذكرة مع فريق الإدارة:\n\n"
            "🛒 **شراء منتج**\n"
            "• للشراء أو الاستفسار عن تفاصيل والأسعار.\n\n"
            "🛠️ **الدعم الفني**\n"
            "• للمشاكل التقنية، والاستفسارات العامة.\n\n"
            "⚠️ *ملاحظة: يحق لك فتح تذكرة واحدة فقط في نفس الوقت.*"
        ),
        color=EMBED_COLOR
    )
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
        embed.set_footer(text="نظام التقييمات المعتمد")
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
# ==================== أوامر الـ Say =====================
# =========================================================

@bot.command(name="say")
async def say(ctx: commands.Context, *, message: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    await ctx.send(message)


@bot.command(name="say-embed")
async def say_embed(ctx: commands.Context, *, message: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(description=message, color=EMBED_COLOR)
    await ctx.send(embed=embed)


# ---------- +say-photo ----------
@bot.command(name="say-photo")
async def say_photo(ctx: commands.Context, *, message: str = None):
    if not ctx.message.attachments:
        await ctx.reply("⚠️ **يجب إرفاق صورة مع الأمر.**", mention_author=False, delete_after=6)
        return

    attachment = ctx.message.attachments[0]
    if not (attachment.content_type and attachment.content_type.startswith("image/")):
        await ctx.reply("⚠️ **الملف المرفق يجب أن يكون صورة.**", mention_author=False, delete_after=6)
        return

    img_bytes = await attachment.read()
    file = discord.File(io.BytesIO(img_bytes), filename=attachment.filename)

    try:
        await ctx.message.delete()
    except Exception:
        pass

    if message:
        await ctx.send(content=message, file=file)
    else:
        await ctx.send(file=file)


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
        await ctx.send(f"✅ **تم إرسال البرودكاست إلى {member.mention} بنجاح.**", delete_after=5)
    except discord.Forbidden:
        await ctx.send(f"❌ **تعذر الإرسال لـ {member.mention} (الخاص مقفل).**", delete_after=5)


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
