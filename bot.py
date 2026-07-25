import os
import re
import json
import math
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
CONFIG_FILE = "config.json"

# ==== الإعدادات الأساسية ====
DEFAULT_WELCOME_CHANNEL_ID = 1526255263462461530
DEFAULT_REVIEWS_CHANNEL_ID = 1513286580456919151
CUSTOMER_ROLE_ID = 1530380565130514583  # رتبة العميل المحددة

# ==== أيديات رتب التذاكر ====
BUY_ROLE_ID = 1530380477377024200      # رتبة الشراء
SUPPORT_ROLE_ID = 1530413725578694746  # رتبة الدعم الفني

# ==== آيدي الشخص المسموح له بـ +cv ====
ALLOWED_USER_ID = 1426552057984454817

STAR_EMOJI = "⭐"
EMBED_COLOR = discord.Color.from_rgb(47, 49, 54) # لون أنيق وفاخر

DEFAULT_PAYMENT_METHODS = {
    "مدار": "لايوجد",
    "ليبيانا": "لايوجد",
    "بايننس": "لايوجد",
    "LTC": "لايوجد",
    "كريديت": "لايوجد"
}

processing_messages = set()


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
        "payment_methods": DEFAULT_PAYMENT_METHODS
    }


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


config = load_config()
if "payment_methods" not in config:
    config["payment_methods"] = DEFAULT_PAYMENT_METHODS
    save_config(config)

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)


# ---------- تقييد استخدام الأوامر العادية لمن يملك Administrator ----------
@bot.check
async def restrict_to_admin(ctx: commands.Context):
    if ctx.guild is None:
        return False
    # استثناء أمر cv ليسمح لصاحب الآيدي فقط
    if ctx.command and ctx.command.name == "cv":
        return True
    return ctx.author.guild_permissions.administrator


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ **عذراً، هذا الأمر مخصص فقط لإدارة السيرفر.**", mention_author=False)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"⚠️ **الرجاء كتابة المعطى المطلوب:** `{error.param.name}`", mention_author=False)
    elif isinstance(error, commands.BadArgument):
        await ctx.reply("⚠️ **تأكد من صحة البيانات أو المنشن المدخل.**", mention_author=False)
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"خطأ غير متوقع: {error}")


@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول بنجاح باسم: {bot.user}")
    activity = discord.Game(name="DEV BY : D0JW")
    await bot.change_presence(activity=activity)


# ---------- دالة استخراج وتحويل المبالغ (دعم k, m, b) ----------
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


# ---------- نظام الترحيب ----------
@bot.event
async def on_member_join(member: discord.Member):
    channel_id = config.get("welcome_channel_id", DEFAULT_WELCOME_CHANNEL_ID)
    channel = member.guild.get_channel(channel_id)
    if channel is None:
        return

    embed = discord.Embed(
        title="✨ أهلاً بك في السيرفر ✨",
        description=(
            f"مرحباً بك {member.mention} في **{member.guild.name}** 🌸\n"
            f"نتمنى لك أوقاتاً ممتعة وتجربة رائعة معنا!"
        ),
        color=discord.Color.from_rgb(88, 101, 242)
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 العضو", value=member.mention, inline=True)
    embed.add_field(name="📊 الترتيب", value=f"**#{member.guild.member_count}**", inline=True)
    embed.add_field(
        name="📅 إنشاء الحساب",
        value=f"<t:{int(member.created_at.timestamp())}:R>",
        inline=True,
    )
    embed.set_footer(text=f"{member.guild.name} • Welcome System", icon_url=member.guild.icon.url if member.guild.icon else None)
    embed.timestamp = discord.utils.utcnow()

    await channel.send(content=f"🎉 **انضمام جديد:** {member.mention}", embed=embed)


# ---------- الرد التلقائي وحساب الضريبة ----------
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
                await message.reply(f"**المبلغ مع الضريبة:** `{total_with_tax}`", mention_author=False)

        await bot.process_commands(message)
    finally:
        processing_messages.discard(message.id)


# =========================================================
# ===================== أمر CV الخاص =======================
# =========================================================

@bot.command(name="cv")
async def cv_command(ctx: commands.Context):
    # مسح الرسالة مباشرة
    try:
        await ctx.message.delete()
    except Exception:
        pass

    # التأكد من صاحب الآيدي المحدد فقط
    if ctx.author.id != ALLOWED_USER_ID:
        return

    guild = ctx.guild
    channel = ctx.channel

    # إعداد الصلاحيات
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.author: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
    }

    # إضافة رتبة الشراء إذا كانت موجودة
    buy_role = guild.get_role(BUY_ROLE_ID)
    if buy_role:
        overwrites[buy_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    # إضافة رتبة الدعم الفني إذا كانت موجودة
    support_role = guild.get_role(SUPPORT_ROLE_ID)
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    # إعطاء صلاحيات لرتب الإدارة العالية
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    # تطبيق التغييرات صامتاً
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
            description=f"✅ **تم منح رتبة {role.mention} إلى {member.mention} بنجاح!** 🎉",
            color=discord.Color.green()
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
        title="🛠️ قائمة الأوامر والتحكم",
        description="البريفكس المعتمد: `+`\n*جميع الأوامر تتطلب صلاحيات الإدارة العليا.*",
        color=EMBED_COLOR,
    )
    
    embed.add_field(
        name="👑 الأوامر الإدارية العامة",
        value=(
            "`+cus <@العضو>` • إعطاء رتبة العميل فوراً\n"
            "`+come <@العضو>` • استدعاء عضو إلى التذكرة\n"
            "`+font <النص>` • زخرفة النص بشكل فخم\n"
            "`+say <الرسالة>` • إرسال نص باسم البوت\n"
            "`+say-embed <الرسالة>` • إرسال إيمبد منسق"
        ),
        inline=False
    )
    embed.add_field(
        name="⚙️ إعدادات المتجر والتذاكر",
        value=(
            "`+panel` • إرسال لوحة فتح التذاكر\n"
            "`+setpay` • إعداد وتحديث طرق الدفع\n"
            "`+pay` • عرض طرق الدفع الحالية\n"
            "`+tax` • تعيين روم حساب الضريبة\n"
            "`+rate <@المشتري> <المنتج>` • طلب تقييم من المشتري\n"
            "`+rate-setup <ID>` • تعيين روم التقييمات\n"
            "`+setup-welcome <ID>` • تعيين روم الترحيب"
        ),
        inline=False
    )
    embed.add_field(
        name="📢 البرودكاست والفعاليات",
        value=(
            "`+giveaway <الدقائق> <الجائزة>` • إنشاء قيفاوي\n"
            "`+bcall <الرسالة>` • إرسال خاص للكل\n"
            "`+bc-role <@الرتبة> <الرسالة>` • إرسال خاص لرتبة\n"
            "`+bc_online <الرسالة>` • إرسال للمتواجدين أونلاين"
        ),
        inline=False
    )
    embed.set_footer(text=f"{ctx.guild.name} • Control Panel", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    await ctx.reply(embed=embed, mention_author=False)


# ---------- +tax (تحديد روم الضريبة) ----------
@bot.command(name="tax", aliases=["tax-setup"])
async def tax_setup(ctx: commands.Context):
    config["tax_channel_id"] = ctx.channel.id
    save_config(config)
    
    await ctx.reply(
        f"✅ **تم اعتماد قناة {ctx.channel.mention} لحساب الضريبة تلقائياً.**",
        mention_author=False
    )


# ---------- +ping ----------
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    await ctx.reply(f"⚡ **سرعة الاتصال:** `{latency}ms`", mention_author=False)


# ---------- +serverinfo ----------
@bot.command(name="serverinfo")
async def serverinfo(ctx: commands.Context):
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 معلومات سيرفر: {guild.name}", color=EMBED_COLOR)
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
    fancy_chars  = "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐉𝐤𝐥𝐦𝐧𝐨𝐩𝐐𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"
    
    trans_table = str.maketrans(normal_chars, fancy_chars)
    fancy_result = text.translate(trans_table)

    embed = discord.Embed(
        title="✨ زخرفة النصوص الاحترافية",
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
        title="📩 استدعاء إلى التذكرة",
        description=(
            f"مرحباً {member.mention} 👋\n\n"
            f"فريق الإدارة بانتظارك في الروم التالي:\n"
            f"📌 **[{ctx.channel.name}]({channel_link})**\n\n"
            f"يرجى التوجه إلى القناة في أقرب وقت."
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
    embed.timestamp = discord.utils.utcnow()

    try:
        await member.send(embed=embed)
        await ctx.reply(f"✅ **تم إرسال الإشعار بنجاح إلى {member.mention}**", mention_author=False)
    except discord.Forbidden:
        await ctx.reply(f"❌ **لم نتمكن من إرسال الرسالة لـ {member.mention} (الخاص مقفل).**", mention_author=False)


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
    libyana = discord.ui.TextInput(label="رقم ليبيانا", placeholder="أدخل الرقم هنا...", required=False)
    madar = discord.ui.TextInput(label="رقم المدار", placeholder="أدخل الرقم هنا...", required=False)
    binance = discord.ui.TextInput(label="بايننس (Binance)", placeholder="أدخل العنوان هنا...", required=False)
    ltc = discord.ui.TextInput(label="عنوان لايتكوين (LTC)", placeholder="أدخل العنوان هنا...", required=False)
    credit = discord.ui.TextInput(label="رصيد / كريديت", placeholder="أدخل البيانات هنا...", required=False)

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
        description="**اختر طريقة الدفع المناسبة لك واستخدم البيانات الموضحة أدناه:**",
        color=EMBED_COLOR
    )
    
    embed.add_field(name="📞 ليبيانا", value=f"`{payments.get('ليبيانا', 'لايوجد')}`", inline=False)
    embed.add_field(name="📱 مدار", value=f"`{payments.get('مدار', 'لايوجد')}`", inline=False)
    embed.add_field(name="🟡 بايننس", value=f"`{payments.get('بايننس', 'لايوجد')}`", inline=False)
    embed.add_field(name="🏛️ لايت كوين", value=f"`{payments.get('LTC', 'لايوجد')}`", inline=False)
    embed.add_field(name="💳 كريديت", value=f"`{payments.get('كريديت', 'لايوجد')}`", inline=False)
    embed.set_footer(text="يرجى التأكد من المبالغ وإرسال الإثبات في التذكرة.")

    await ctx.send(embed=embed)


# =========================================================
# ===================== نظام التذاكر ======================
# =========================================================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التذكرة", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and not interaction.channel.name.endswith(str(interaction.user.id)[-4:]):
            await interaction.response.send_message("❌ **ليس لديك صلاحية لإغلاق هذه التذكرة.**", ephemeral=True)
            return

        await interaction.response.send_message("🔒 **جاري قفل التذكرة...**", ephemeral=True)
        
        for target, overwrite in interaction.channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot:
                overwrite.send_messages = False
                try:
                    await interaction.channel.set_permissions(target, overwrite=overwrite)
                except Exception:
                    pass
        
        await interaction.followup.send("⚠️ **تم قفل التذكرة بنجاح. يمكنك حذف الروم عبر الزر أدناه:**", view=TicketDeleteView())


class TicketDeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="حذف التذكرة", emoji="🗑️", style=discord.ButtonStyle.secondary, custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ **هذا الزر مخصص للإدارة فقط.**", ephemeral=True)
            return
        
        await interaction.response.send_message("🗑️ **جاري حذف التذكرة خلال 3 ثوانٍ...**", ephemeral=True)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


class TicketSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _create_ticket_channel(self, interaction: discord.Interaction, prefix: str, title_msg: str, role_id: int):
        guild = interaction.guild
        member = interaction.user

        existing_channel = discord.utils.get(guild.text_channels, name=f"{prefix}-{member.name.lower()[:8]}")
        if existing_channel:
            await interaction.response.send_message(f"❌ **لديك تذكرة مفتوحة بالفعل:** {existing_channel.mention}", ephemeral=True)
            return

        await interaction.response.send_message("⏳ **جاري فتح التذكرة الخاصة بك...**", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

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

        embed = discord.Embed(
            title=title_msg,
            description=f"أهلاً بك {member.mention}\nيرجى توضيح طلبك بالتفصيل وسيقوم الفريق بالرد عليك في أقرب وقت.",
            color=EMBED_COLOR
        )
        embed.set_footer(text=f"{guild.name} • Axion Store", icon_url=guild.icon.url if guild.icon else None)

        mention_content = f"{member.mention} <@&{role_id}>"
        await ticket_channel.send(content=mention_content, embed=embed, view=TicketControlView())

    @discord.ui.button(
        label="شراء منتج", 
        emoji="🛒", 
        style=discord.ButtonStyle.success, 
        custom_id="buy_ticket"
    )
    async def buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket_channel(interaction, "buy", "🛒 تذكرة شراء منتج", BUY_ROLE_ID)

    @discord.ui.button(
        label="الدعم الفنى", 
        emoji="🛠️", 
        style=discord.ButtonStyle.primary, 
        custom_id="support_ticket"
    )
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket_channel(interaction, "support", "🛠️ تذكرة الدعم الفني والاستفسارات", SUPPORT_ROLE_ID)


@bot.command(name="panel")
async def panel_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    embed = discord.Embed(
        title="🎫 مركز الشراء والدعم الفني",
        description=(
            "اختر نوع التذكرة المناسب، وسيقوم الفريق بمراجعة طلبك ومساعدتك بأسرع وقت.\n\n"
            "🛒 **شراء منتج**\n"
            "• لشراء أو الاستفسار عن تفاصيل المنتجات والأسعار المتاحة.\n\n"
            "🛠️ **الدعم الفني**\n"
            "• للمشاكل التقنية، الاستفسارات، أو أي مساعدة تخص السيرفر.\n\n"
            "*يرجى اختيار النوع الصحيح وكتابة التفاصيل بوضوح.*"
        ),
        color=EMBED_COLOR
    )
    embed.set_footer(text="DEV BY : @D0JW")

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
                f"**تم إرسال التقييم بواسطة:** {self.buyer.mention}\n\n"
                f"📦 **البائع:** {self.seller.mention}\n"
                f"🛍️ **المنتج:** `{self.product}`\n\n"
                f"🌟 **التقييم:** {stars}\n\n"
                f"💬 **التعليق:**\n```{self.comment.value}```"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="نظام التقييمات المعتمد")
        embed.timestamp = discord.utils.utcnow()

        reviews_channel_id = config.get("reviews_channel_id", DEFAULT_REVIEWS_CHANNEL_ID)
        reviews_channel = bot.get_channel(reviews_channel_id)
        if reviews_channel:
            await reviews_channel.send(embed=embed)
            await interaction.response.send_message("✅ **شكراً جزيلاً على تقييمك العطر!**", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ **ما قدرت ألقى روم التقييمات.**", ephemeral=True)

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
        color=discord.Color.gold()
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


# =========================================================
# ==================== نظام القيفاوي ======================
# =========================================================

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="مشاركة في المسابقة", emoji="🎉", style=discord.ButtonStyle.success, custom_id="join_giveaway")
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🎉 **تم تسجيل مشاركتك بنجاح! بالتوفيق.**", ephemeral=True)


@bot.command(name="giveaway")
async def giveaway(ctx: commands.Context, minutes: int, *, prize: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    
    end_time = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
    
    embed = discord.Embed(
        title="🎁 **مسابقة جديدة (GIVEAWAY)** 🎁",
        description=f"🏆 **الجائزة:** `{prize}`\n\nاضغط على الزر أدناه لإنشاء مشاركتك!\n\n⏰ **تنتهي المسابقة:** <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"بواسطة: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
    view = GiveawayView()
    await ctx.send(embed=embed, view=view)


# =========================================================
# =================== نظام البرودكاست ====================
# =========================================================

async def _send_broadcast(ctx: commands.Context, members: list, message: str, label: str):
    status_msg = await ctx.reply(f"⏳ **جاري بدء إرسال {label} لـ {len(members)} عضو...**", mention_author=False)

    sent, failed = 0, 0
    embed = discord.Embed(
        title=f"📢 إعلان رسمي من {ctx.guild.name}",
        description=message,
        color=discord.Color.gold(),
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
