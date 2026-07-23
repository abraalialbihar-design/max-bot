import os
import json
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CONFIG_FILE = "config.json"

# ==== الإعدادات ====
DEFAULT_WELCOME_CHANNEL_ID = 1526255263462461530
NICKNAME_TRIGGER_CHANNEL_ID = 1529710377976336434
NICKNAME_PREFIX = "𝐌𝐗 | "
ADMIN_ROLE_ID = 1529955905548849232  # الرتبة الوحيدة المسموح لها تستخدم الأوامر الإدارية
# ====================


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "welcome_channel_id": DEFAULT_WELCOME_CHANNEL_ID
    }


def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


config = load_config()

intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="+", intents=intents, help_command=None)


# ---------- تقييد استخدام الأوامر على رتبة معينة ----------
@bot.check
async def restrict_to_admin_role(ctx: commands.Context):
    if ctx.guild is None:
        return False
    return any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.reply("❌ هذا الأمر مخصص فقط لأصحاب الرتبة المصرح لها.", mention_author=False)
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
    
    # تعيين حالة البوت
    activity = discord.Game(name="MAX SERVER | SERVER: https://discord.gg/ba2u2s4mz | DEVOLPER: d0jw")
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


# ---------- تعديل النيك التلقائي + الرد التلقائي (AutoReply) + الأوامر ----------
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    member = message.author

    # 1. نظام الرد التلقائي (لو رسل كلمة شعار)
    if message.content.strip() == "شعار":
        await message.reply("𝐌𝐗 |", mention_author=False)

    # 2. نظام تعديل النيك التلقائي
    if message.channel.id == NICKNAME_TRIGGER_CHANNEL_ID:
        current_name = member.display_name
        if not current_name.startswith(NICKNAME_PREFIX):
            try:
                await member.edit(nick=f"{NICKNAME_PREFIX}{current_name}", reason="تعديل تلقائي عند الكتابة في الروم المحدد")
            except Exception:
                pass

    await bot.process_commands(message)


# =========================================================
# ========================  +help  ========================
# =========================================================

@bot.command(name="help")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="📖 قائمة أوامر البوت",
        description="البريفكس: `+`\nكل الأوامر الإدارية مخصصة فقط للرتبة المصرح لها",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="+ping", value="يعرض زمن استجابة البوت", inline=False)
    embed.add_field(name="+serverinfo", value="يعرض معلومات عن السيرفر", inline=False)
    embed.add_field(name="+font <النص>", value="يزخرف النص بالنمط الفخم", inline=False)
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


bot.run(TOKEN)