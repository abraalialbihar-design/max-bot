import os
import json
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
STAR_EMOJI = "⭐"

DEFAULT_PAYMENT_METHODS = {
    "مدار": "لايوجد",
    "ليبيانا": "لايوجد",
    "بايننس": "لايوجد",
    "LTC": "لايوجد",
    "كريديت": "لايوجد"
}
# ===========================


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


# ---------- تقييد استخدام الأوامر لمن يملك Administrator فقط ----------
@bot.check
async def restrict_to_admin(ctx: commands.Context):
    if ctx.guild is None:
        return False
    return ctx.author.guild_permissions.administrator


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ هذا الأمر مخصص فقط لمن يمتلك صلاحية **Administrator** في السيرفر.", mention_author=False)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"⚠️ ناقص معطى مطلوب: `{error.param.name}`", mention_author=False)
    elif isinstance(error, commands.BadArgument):
        await ctx.reply("⚠️ تأكد أن المعطيات أو الأيديات التي كتبتها صحيحة.", mention_author=False)
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        print(f"خطأ غير متوقع: {error}")
        await ctx.reply("❌ حدث خطأ أثناء تنفيذ الأمر.", mention_author=False)


@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول باسم {bot.user}")
    activity = discord.Game(name="DEV BY : D0JW")
    await bot.change_presence(activity=activity)


# ---------- نظام الترحيب ----------
@bot.event
async def on_member_join(member: discord.Member):
    channel_id = config.get("welcome_channel_id", DEFAULT_WELCOME_CHANNEL_ID)
    channel = member.guild.get_channel(channel_id)
    if channel is None:
        return

    embed = discord.Embed(
        title="✨ عضو جديد انضم للعائلة ✨",
        description=(
            f"### أهلاً بك {member.mention} 👋\n"
            f"يسعدنا انضمامك إلى **{member.guild.name}**\n"
            f"نتمنى لك إقامة ممتعة وأوقات حلوة معنا 🌸"
        ),
        color=discord.Color.from_rgb(88, 101, 242),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤 العضو", value=member.mention, inline=True)
    embed.add_field(name="📊 ترتيبه", value=f"العضو رقم **{member.guild.member_count}**", inline=True)
    embed.add_field(
        name="📅 تاريخ إنشاء الحساب",
        value=f"<t:{int(member.created_at.timestamp())}:D>",
        inline=True,
    )
    embed.set_footer(text=f"{member.guild.name} • نتمنى لك وقتاً ممتعاً", icon_url=member.guild.icon.url if member.guild.icon else None)
    embed.timestamp = discord.utils.utcnow()

    await channel.send(content=f"🎉 {member.mention} وصل للتو!", embed=embed)


# ---------- الرد التلقائي ----------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    if message.content.strip() == "شعار":
        await message.reply("𝐌𝐗 |", mention_author=False)

    await bot.process_commands(message)


# =========================================================
# ========================  +help  ========================
# =========================================================

@bot.command(name="help")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="📖 قائمة أوامر البوت",
        description="البريفكس: `+`\nكل الأوامر الإدارية تتطلب صلاحية **Administrator**",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="+ping", value="يعرض زمن استجابة البوت", inline=False)
    embed.add_field(name="+serverinfo", value="يعرض معلومات عن السيرفر", inline=False)
    embed.add_field(name="+font <النص>", value="يزخرف النص بالنمط الفخم", inline=False)
    embed.add_field(name="+come <@العضو>", value="إرسال تنبيه للعضو للقدوم إلى التذكرة", inline=False)
    embed.add_field(name="+pay", value="عرض طرق الدفع المعتمدة", inline=False)
    embed.add_field(name="+setpay", value="فتح قائمة لتعديل وحفظ بيانات طرق الدفع", inline=False)
    embed.add_field(name="+ticket-setup", value="يرسل لوحة التذاكر الاحترافية في الروم الحالي", inline=False)
    embed.add_field(name="+rate <@المشتري> <المنتج>", value="طلب تقييم من المشتري", inline=False)
    embed.add_field(name="+rate-setup <آيدي_الروم>", value="يحدد روم إرسال التقييمات", inline=False)
    embed.add_field(name="+setup-welcome <آيدي_الروم>", value="يحدد روم رسائل الترحيب", inline=False)
    embed.add_field(name="+giveaway <الدقائق> <الجائزة>", value="يبدأ مسابقة قيفاوي جديدة", inline=False)
    embed.add_field(name="+say <الرسالة>", value="يرسل رسالة عادية على لسان البوت", inline=False)
    embed.add_field(name="+say-embed <الرسالة>", value="يرسل رسالة إيمبد منسقة", inline=False)
    embed.add_field(name="+bcall <الرسالة>", value="يرسل رسالة خاصة لكل أعضاء السيرفر", inline=False)
    embed.add_field(name="+bc-role <@الرتبة> <الرسالة>", value="يرسل رسالة خاصة لأعضاء رتبة معينة", inline=False)
    embed.add_field(name="+bc_online <الرسالة>", value="يرسل رسالة خاصة لكل المتواجدين أونلاين", inline=False)
    embed.set_footer(text=ctx.guild.name)
    await ctx.reply(embed=embed, mention_author=False)


# ---------- +ping ----------
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    await ctx.reply(f"🏓 Pong! زمن الاستجابة: **{latency}ms**", mention_author=False)


# ---------- +serverinfo ----------
@bot.command(name="serverinfo")
async def serverinfo(ctx: commands.Context):
    guild = ctx.guild
    embed = discord.Embed(title=f"معلومات سيرفر: {guild.name}", color=discord.Color.blurple())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="عدد الأعضاء", value=str(guild.member_count), inline=True)
    embed.add_field(name="المالك", value=f"<@{guild.owner_id}>", inline=True)
    embed.add_field(name="تاريخ الإنشاء", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
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
        title="✨ النص المزخرف",
        description=f"**النص الأصلي:** {text}\n**بعد الزخرفة:**\n```{fancy_result}```",
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"بواسطة: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
    await ctx.send(embed=embed)


# ---------- +come ----------
@bot.command(name="come")
async def come_command(ctx: commands.Context, member: discord.Member):
    channel_name = ctx.channel.name
    channel_link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}"
    message = (
        f"📩 لديك رسالة جديدة في التذكرة\n"
        f"مرحباً {member.mention}\n"
        f"صاحب التذكرة في انتظار ردك في **{channel_name}**\n"
        f"يرجى الرد في أقرب وقت ممكن.\n"
        f"📌 القناة: {channel_link}\n"
        f"👤 بواسطة: {ctx.author.name}"
    )
    try:
        await member.send(message)
        await ctx.reply(f"✅ تم إرسال التنبيه إلى {member.mention}", mention_author=False)
    except discord.Forbidden:
        await ctx.reply(f"❌ ما قدرت أرسل لـ {member.mention} — الخاص مقفل.", mention_author=False)
    except discord.HTTPException as e:
        await ctx.reply(f"❌ حدث خطأ أثناء الإرسال: {e}", mention_author=False)


# ---------- +setup-welcome ----------
@bot.command(name="setup-welcome")
async def setup_welcome(ctx: commands.Context, channel_id: int):
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.reply("❌ ما لقيت روم بهذا الآيدي في السيرفر.", mention_author=False)
        return

    config["welcome_channel_id"] = channel.id
    save_config(config)
    await ctx.reply(f"✅ تم تحديد {channel.mention} كروم رسمي لرسائل الترحيب.", mention_author=False)


# ---------- +rate-setup ----------
@bot.command(name="rate-setup")
async def rate_setup(ctx: commands.Context, channel_id: int):
    channel = ctx.guild.get_channel(channel_id)
    if channel is None:
        await ctx.reply("❌ ما لقيت روم بهذا الآيدي في السيرفر.", mention_author=False)
        return

    config["reviews_channel_id"] = channel.id
    save_config(config)
    await ctx.reply(f"✅ تم تحديد {channel.mention} كروم رسمي لتلقي التقييمات.", mention_author=False)


# =========================================================
# ==================== نظام الدفع (+pay / +setpay) ==================
# =========================================================

class SetPayModal(discord.ui.Modal, title="تحديد طرق الدفع"):
    libyana = discord.ui.TextInput(
        label="رقم ليبيانا",
        placeholder="أدخل الرقم هنا أو اتركه فارغاً",
        required=False
    )
    madar = discord.ui.TextInput(
        label="رقم المدار",
        placeholder="أدخل الرقم هنا أو اتركه فارغاً",
        required=False
    )
    binance = discord.ui.TextInput(
        label="بايننس",
        placeholder="أدخل العنوان هنا أو اتركه فارغاً",
        required=False
    )
    ltc = discord.ui.TextInput(
        label="عنوان لايتكوين (LTC)",
        placeholder="أدخل العنوان هنا أو اتركه فارغاً",
        required=False
    )
    credit = discord.ui.TextInput(
        label="رصيد / كريديت",
        placeholder="أدخل الرقم هنا أو اتركه فارغاً",
        required=False
    )

    def __init__(self):
        super().__init__()
        self.libyana.default = None
        self.madar.default = None
        self.binance.default = None
        self.ltc.default = None
        self.credit.default = None

    async def on_submit(self, interaction: discord.Interaction):
        config["payment_methods"] = {
            "ليبيانا": self.libyana.value.strip() or "لايوجد",
            "مدار": self.madar.value.strip() or "لايوجد",
            "بايننس": self.binance.value.strip() or "لايوجد",
            "LTC": self.ltc.value.strip() or "لايوجد",
            "كريديت": self.credit.value.strip() or "لايوجد"
        }
        save_config(config)
        await interaction.response.send_message("✅ تم حفظ طرق الدفع بنجاح!", ephemeral=True)


class SetPayView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id

    @discord.ui.button(label="✏️ تعديل طرق الدفع", style=discord.ButtonStyle.primary)
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ هذا الأمر لمن استخدم +setpay فقط.", ephemeral=True)
            return
        await interaction.response.send_modal(SetPayModal())


@bot.command(name="setpay")
async def setpay_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    view = SetPayView(author_id=ctx.author.id)
    await ctx.send("اضغط على الزر أدناه لفتح قائمة تعبئة بيانات طرق الدفع:", view=view)


@bot.command(name="pay")
async def pay_command(ctx: commands.Context):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    payments = config.get("payment_methods", DEFAULT_PAYMENT_METHODS)

    embed = discord.Embed(
        title="💳 طرق الدفع المعتمدة",
        color=discord.Color.from_rgb(47, 49, 54)
    )
    
    embed.add_field(name="📞 ليبيانا", value=f"`{payments.get('ليبيانا', 'لايوجد')}`", inline=False)
    embed.add_field(name="📱 مدار", value=f"`{payments.get('مدار', 'لايوجد')}`", inline=False)
    embed.add_field(name="🟡 بايننس", value=f"`{payments.get('بايننس', 'لايوجد')}`", inline=False)
    embed.add_field(name="🏛️ لايت كوين", value=f"`{payments.get('LTC', 'لايوجد')}`", inline=False)
    embed.add_field(name="💳 كريديت", value=f"`{payments.get('كريديت', 'لايوجد')}`", inline=False)

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
            await interaction.response.send_message("❌ ليس لديك صلاحية لإغلاق هذه التذكرة.", ephemeral=True)
            return

        await interaction.response.send_message("🔒 جاري إغلاق التذكرة...", ephemeral=True)
        
        for target, overwrite in interaction.channel.overwrites.items():
            if isinstance(target, discord.Member) and not target.bot:
                overwrite.send_messages = False
                try:
                    await interaction.channel.set_permissions(target, overwrite=overwrite)
                except Exception:
                    pass
        
        await interaction.followup.send("⚠️ تم قفل التذكرة بنجاح. يمكنك حذفها عبر الزر أدناه.", view=TicketDeleteView())


class TicketDeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="حذف التذكرة", emoji="🗑️", style=discord.ButtonStyle.secondary, custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ هذا الزر مخصص للأدمن فقط.", ephemeral=True)
            return
        
        await interaction.response.send_message("🗑️ جاري حذف الروم نهائياً خلال 3 ثوانٍ...", ephemeral=True)
        await asyncio.sleep(3)
        try:
            await interaction.channel.delete()
        except Exception:
            pass


class TicketSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _create_ticket_channel(self, interaction: discord.Interaction, prefix: str, title_msg: str):
        guild = interaction.guild
        member = interaction.user

        existing_channel = discord.utils.get(guild.text_channels, name=f"{prefix}-{member.name.lower()[:8]}")
        if existing_channel:
            await interaction.response.send_message(f"❌ لديك تذكرة مفتوحة من هذا النوع مسبقاً هنا: {existing_channel.mention}", ephemeral=True)
            return

        await interaction.response.send_message("⏳ جاري إنشاء تذكرتك الخاصة...", ephemeral=True)

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
            description=f"أهلاً بك {member.mention}\nيرجى توضيح طلبك بالتفصيل وسيتم الرد عليك في أقرب وقت من قِبل الإدارة.",
            color=discord.Color.from_rgb(47, 49, 54)
        )
        embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)

        await ticket_channel.send(content=f"{member.mention}", embed=embed, view=TicketControlView())

    @discord.ui.button(
        label="شراء منتج", 
        emoji="🛒", 
        style=discord.ButtonStyle.success, 
        custom_id="buy_ticket"
    )
    async def buy_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket_channel(interaction, "buy", "🛒 تذكرة شراء منتج")

    @discord.ui.button(
        label="الدعم الفنى", 
        emoji="🛠️", 
        style=discord.ButtonStyle.primary, 
        custom_id="support_ticket"
    )
    async def support_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._create_ticket_channel(interaction, "support", "🛠️ تذكرة الدعم الفني والاستفسارات")


@bot.command(name="ticket-setup")
async def ticket_setup(ctx: commands.Context):
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
        color=discord.Color.from_rgb(47, 49, 54)
    )
    embed.set_footer(text="DEV BY : @D0JW")

    await ctx.send(embed=embed, view=TicketSetupView())


# =========================================================
# ================= نظام التقييمات: +rate ==================
# =========================================================

class RateModal(discord.ui.Modal, title="تقييم عملية الشراء"):
    rating = discord.ui.TextInput(label="التقييم (من 1 إلى 5)", placeholder="5", max_length=1, required=True)
    comment = discord.ui.TextInput(label="التعليق", style=discord.TextStyle.paragraph, placeholder="اكتب رأيك بالخدمة...", required=True, max_length=300)

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
                f"تم ارسال هذا التقييم من: **({self.buyer.mention}) {self.buyer.name}**\n\n"
                f"📦 **البائع:** ({self.seller.mention}) {self.seller.name}\n\n"
                f"🛍️ **نوع المنتج:** {self.product}\n\n"
                f"**التقييم:** {stars}\n\n"
                f"💬 **التعليق:**\n{self.comment.value}"
            ),
            color=discord.Color.from_rgb(255, 215, 0)
        )
        embed.set_footer(text="نظام التقييمات • MAYBE STORE")
        embed.timestamp = discord.utils.utcnow()

        reviews_channel_id = config.get("reviews_channel_id", DEFAULT_REVIEWS_CHANNEL_ID)
        reviews_channel = bot.get_channel(reviews_channel_id)
        if reviews_channel:
            await reviews_channel.send(embed=embed)
            await interaction.response.send_message("✅ شكراً على تقييمك!", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ ما قدرت ألقى روم التقييمات، تأكد من إعداده عبر `+rate-setup`.", ephemeral=True)

        self.rate_view.rate_button.disabled = True
        self.rate_view.rate_button.label = "تم التقييم مسبقاً ✅"
        await interaction.message.edit(view=self.rate_view)


class RateView(discord.ui.View):
    def __init__(self, seller: discord.Member, buyer: discord.Member, product: str):
        super().__init__(timeout=None)
        self.seller = seller
        self.buyer = buyer
        self.product = product

    @discord.ui.button(label="اضغط لتقييم المنتج", style=discord.ButtonStyle.success, emoji="⭐")
    async def rate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.buyer.id:
            await interaction.response.send_message("❌ هذا التقييم مخصص لشخص ثاني، مو لك.", ephemeral=True)
            return
        await interaction.response.send_modal(RateModal(self.seller, self.buyer, self.product, self))


def build_rate_embed(buyer: discord.Member):
    return discord.Embed(
        description=f"{buyer.mention} 👋 شكراً لثقتك فينا!\nنتمنى منك تقييم عملية الشراء بالضغط على الزر تحت.",
        color=discord.Color.from_rgb(255, 215, 0)
    )

@bot.command(name="rate")
async def rate_prefix(ctx: commands.Context, buyer: discord.Member, *, product: str):
    view = RateView(seller=ctx.author, buyer=buyer, product=product)
    await ctx.send(embed=build_rate_embed(buyer), view=view)


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
    
    embed = discord.Embed(
        description=message,
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)


# =========================================================
# ==================== نظام القيفاوي ======================
# =========================================================

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="مشاركة", emoji="🎉", style=discord.ButtonStyle.success, custom_id="join_giveaway")
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ تم تسجيل مشاركتك في المسابقة بنجاح!", ephemeral=True)


@bot.command(name="giveaway")
async def giveaway(ctx: commands.Context, minutes: int, *, prize: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    
    end_time = discord.utils.utcnow() + discord.timedelta(minutes=minutes)
    
    embed = discord.Embed(
        title="🎉 **قيفاوي جديد (GIVEAWAY)** 🎉",
        description=f"الـجـائـزة: **{prize}**\n\nاضغط على الزر أدناه للمشاركة! 🎁\n\nينتهي في: <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.gold()
    )
    embed.set_footer(text=f"بواسطة: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
    view = GiveawayView()
    await ctx.send(embed=embed, view=view)


# =========================================================
# =================== نظام البرودكاست ====================
# =========================================================

async def _send_broadcast(ctx: commands.Context, members: list, message: str, label: str):
    status_msg = await ctx.reply(f"⏳ جارٍ إرسال البرودكاست لـ {len(members)} عضو...", mention_author=False)

    sent, failed = 0, 0
    embed = discord.Embed(
        title=f"📢 إعلان من {ctx.guild.name}",
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
            f"✅ انتهى إرسال {label}\n"
            f"تم الإرسال بنجاح لـ **{sent}** عضو\n"
            f"فشل الإرسال لـ **{failed}** عضو (خاصهم مقفول غالباً)"
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
    await _send_broadcast(ctx, members, message, "برودكاست الأونلاين")


if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم العثور على التوكن في ملف .env (تأكد من وجود DISCORD_TOKEN أو BOT_TOKEN)")
