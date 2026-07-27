import os
import re
import json
import math
import random
import hashlib
import asyncio
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
CONFIG_FILE = "config.json"

# ==== الإعدادات الأساسية ====
DEFAULT_WELCOME_CHANNEL_ID = 1526255263462461530
DEFAULT_REVIEWS_CHANNEL_ID = 1513286580456919151
CUSTOMER_ROLE_ID = 1530380565130514583

# ==== أيديات رتب التذاكر ====
BUY_ROLE_ID = 1530380477377024200      # رتبة الشراء
SUPPORT_ROLE_ID = 1530413725578694746  # رتبة الدعم الفني

# ==== آيدي الشخص المسموح له بـ +cv ====
ALLOWED_USER_ID = 1426552057984454817

EMBED_COLOR = discord.Color.from_rgb(47, 49, 54)

DEFAULT_PAYMENT_METHODS = {
    "مدار": "لايوجد",
    "ليبيانا": "لايوجد",
    "بايننس": "لايوجد",
    "LTC": "لايوجد",
    "كريديت": "لايوجد"
}

# قوانين متجر Axion Store
AXION_TERMS = (
    "📋 **قوانين متجر 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞**\n\n"
    "1️⃣ **1 -** يمنع طلب استبدال السلعة او استرداد الاموال بعد شرائك شي من المتجر ويجب أن تكون متأكدا قبل شرائك.\n\n"
    "2️⃣ **2 -** لا يحق للعميل طلب تخفيض سعر او شيء مجاني من المتجر.\n\n"
    "3️⃣ **3 -** يحق للعميل شراء هدية لشخص من منتجات المتجر.\n\n"
    "4️⃣ **4 -** جميع المشتريات تكون من خلال التذاكر المخصصة للمتجر فقط لا غير."
)

processing_messages = set()
invites_cache = {}          
processed_receipts = set()   


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["terms_text"] = AXION_TERMS
                return data
        except Exception:
            pass
    return {
        "welcome_channel_id": DEFAULT_WELCOME_CHANNEL_ID,
        "reviews_channel_id": DEFAULT_REVIEWS_CHANNEL_ID,
        "tax_channel_id": None,
        "buy_category_id": None,
        "support_category_id": None,
        "payment_methods": DEFAULT_PAYMENT_METHODS,
        "terms_text": AXION_TERMS
    }


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


config = load_config()


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

        # 🔒 شرط فتح تذكرة واحدة فقط لكل عضو
        for channel in guild.text_channels:
            if channel.name.startswith(("buy-", "support-")):
                for target, overwrite in channel.overwrites.items():
                    if target == member and overwrite.view_channel:
                        await interaction.response.send_message(f"⚠️ **لديك تذكرة مفتوحة بالفعل!** {channel.mention}\nيمكنك فتح تذكرة واحدة فقط في نفس الوقت.", ephemeral=True)
                        return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        for role in guild.roles:
            if role.permissions.administrator or role.id in [BUY_ROLE_ID, SUPPORT_ROLE_ID]:
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
    if channel:
        inv_text = f"\n📩 **تم الدعوة بواسطة:** {inviter.mention}" if inviter else ""
        embed = discord.Embed(
            title="✨ أهلاً بك في 𝐀𝐱𝐢𝐨𝐧 𝐒𝐭𝐨𝐫𝐞 ✨",
            description=f"مرحباً بك {member.mention} في **{guild.name}** 🌸{inv_text}",
            color=EMBED_COLOR
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="📊 الترتيب", value=f"**#{guild.member_count}**", inline=True)
        embed.set_footer(text=f"{guild.name} • Welcome", icon_url=guild.icon.url if guild.icon else None)
        await channel.send(content=f"🎉 {member.mention}", embed=embed)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    if message.id in processing_messages:
        return
    processing_messages.add(message.id)

    try:
        # فحص الإيصالات المكررة (Anti-Duplicate Receipts)
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    img_bytes = await attachment.read()
                    img_hash = hashlib.md5(img_bytes).hexdigest()

                    if img_hash in processed_receipts:
                        await message.delete()
                        await message.channel.send(
                            f"⚠️ {message.author.mention} **تحذير:** تم اكتشاف صورة إيصال مكررة تم استخدامها من قبل! تم حذف الرسالة.",
                            delete_after=10
                        )
                        return
                    else:
                        processed_receipts.add(img_hash)

        if message.content.strip() == "شعار":
            await message.reply("𝐌𝐗 |", mention_author=False)

        tax_channel_id = config.get("tax_channel_id")
        if tax_channel_id and message.channel.id == tax_channel_id and not message.content.startswith("+"):
            cleaned = message.content.strip().replace(",", "").lower()
            match = re.match(r"^(\d+(?:\.\d+)?)\s*([kmb])?$", cleaned)
            if match:
                num, suf = match.groups()
                val = float(num)
                if suf == "k": val *= 1_000
                elif suf == "m": val *= 1_000_000
                elif suf == "b": val *= 1_000_000_000
                total = math.ceil(val / 0.95)
                await message.reply(f"💳 **المبلغ مع الضريبة:** `{total:,}`", mention_author=False)

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

    target_time = discord.utils.utcnow() + discord.timedelta(hours=hours)
    embed = discord.Embed(
        title="⏱️ مؤقت تسليم الطلب (Delivery Timer)",
        description=(
            f"تم بدء عداد تسليم الطلب للعميل.\n\n"
            f"⏳ **المدة المحددة:** `{hours}` ساعة\n"
            f"🎯 **موعد التسليم المتوقع:** <t:{int(target_time.timestamp())}:F> (<t:{int(target_time.timestamp())}:R>)"
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
    try: await ctx.message.delete()
    except Exception: pass

    embed = discord.Embed(
        description=f"✅ **تم استلام التذكرة بواسطة:** {ctx.author.mention}\nسيقوم بمتابعة طلبك الآن.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


# ---------- 🧾 مولد الفواتير (+invoice) ----------
@bot.command(name="invoice")
async def create_invoice(ctx: commands.Context, buyer: discord.Member, amount: str = "غير محدد", *, product: str = "منتج"):
    try: await ctx.message.delete()
    except Exception: pass

    inv_id = random.randint(100000, 999999)
    embed = discord.Embed(
        title=f"🧾 فاتورة شراء إلكترونية #{inv_id}",
        color=discord.Color.gold()
    )
    embed.add_field(name="👤 العميل", value=buyer.mention, inline=True)
    embed.add_field(name="👑 البائع / الموظف", value=ctx.author.mention, inline=True)
    embed.add_field(name="🛍️ المنتج / الخدمة", value=f"`{product}`", inline=False)
    embed.add_field(name="💰 المبلغ المدفوع", value=f"`{amount}`", inline=True)
    embed.add_field(name="📅 التاريخ", value=f"<t:{int(ctx.message.created_at.timestamp())}:D>", inline=True)
    embed.set_footer(text=f"{ctx.guild.name} • Axion Store Invoice", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)

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

    embed = discord.Embed(
        description=f"📊 **عدد دعوات {target.mention}:** `{total_uses}` عضو",
        color=EMBED_COLOR
    )
    await ctx.reply(embed=embed, mention_author=False)


# ---------- 🔒 إغلاق التذكرة (+close) ----------
@bot.command(name="close")
async def close_ticket_cmd(ctx: commands.Context):
    await ctx.send("🔒 **تم إغلاق التذكرة. سيتم حذف القناة تلقائياً خلال 5 ثوانٍ...**")
    for target, overwrite in ctx.channel.overwrites.items():
        if isinstance(target, discord.Member) and not target.bot:
            overwrite.send_messages = False
            try: await ctx.channel.set_permissions(target, overwrite=overwrite)
            except Exception: pass
    await asyncio.sleep(5)
    try: await ctx.channel.delete()
    except Exception: pass


# ---------- 👑 منح رتبة العميل (+cus) ----------
@bot.command(name="cus")
async def give_customer_role(ctx: commands.Context, member: discord.Member):
    try: await ctx.message.delete()
    except Exception: pass

    role = ctx.guild.get_role(CUSTOMER_ROLE_ID)
    if not role:
        await ctx.send("❌ **لم يتم العثور على رتبة العميل.**")
        return

    try:
        await member.add_roles(role)
        await ctx.send(embed=discord.Embed(description=f"✨ **تم منح رتبة {role.mention} إلى {member.mention} بنجاح!** 🎉", color=EMBED_COLOR))
    except Exception as e:
        await ctx.send(f"❌ **حدث خطأ:** {e}")


# ---------- 🎫 لوحة التذاكر الرئيسية (+panel) ----------
@bot.command(name="panel")
async def panel_command(ctx: commands.Context):
    try: await ctx.message.delete()
    except Exception: pass

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


# ---------- 🧹 مسح الرسائل (+clear) ----------
@bot.command(name="clear")
async def clear_messages(ctx: commands.Context, amount: int = 100):
    try: await ctx.message.delete()
    except Exception: pass
    deleted = await ctx.channel.purge(limit=amount)
    msg = await ctx.send(f"🧹 **تم مسح `{len(deleted)}` رسالة بنجاح.**")
    await asyncio.sleep(3)
    try: await msg.delete()
    except Exception: pass


# ---------- ⚙️ أمر +cv الخاص ----------
@bot.command(name="cv")
async def cv_command(ctx: commands.Context):
    try: await ctx.message.delete()
    except Exception: pass

    if ctx.author.id != ALLOWED_USER_ID:
        return

    guild = ctx.guild
    channel = ctx.channel

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(send_messages=False),
        ctx.author: discord.PermissionOverwrite(send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
    }

    try:
        await channel.edit(overwrites=overwrites)
    except Exception as e:
        print(f"خطأ +cv: {e}")


# ---------- ⌛ التذكير التلقائي للتذاكر الخاملة ----------
@tasks.loop(hours=1)
async def check_inactive_tickets():
    now = discord.utils.utcnow()
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name.startswith(("buy-", "support-")):
                try:
                    history = [m async for m in channel.history(limit=1)]
                    if history and (now - history[0].created_at).total_seconds() >= 86400:
                        for target in channel.overwrites:
                            if isinstance(target, discord.Member) and not target.bot:
                                embed = discord.Embed(
                                    title="⌛ **تذكير بتذكرة خاملة**",
                                    description=f"مرحباً {target.mention} 👋\nلاحظنا عدم وجود أي تفاعل في التذكرة منذ 24 ساعة.",
                                    color=discord.Color.orange()
                                )
                                await channel.send(content=f"🔔 {target.mention}", embed=embed)
                                break
                except Exception:
                    pass


if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على التوكن في ملف .env")
