import discord
from discord.ext import commands
import datetime

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.presences = True  
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- (قم بتعديل هذه المعرفات بما يناسب سيرفرك) ---
ALLOWED_HOURS_ROLES = [1546454372509159475, 1546470436529901578]  # IDs رتب ساعات
ALLOWED_ONLINE_ROLES = [1546470892916318249, 1546469597681819719] # IDs رتب المتواجدين
OWNER_ROLES = [1546470892916318249]                              # IDs رتب الأونر للأوامر
TARGET_CHANNEL_ID = 1547074613929050183                         # آيدي الروم للوحة التحكم

database = {}
warning_tasks = {}  # لتخزين مؤتمرات المهلة (10 دقائق)

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="تسجيل دخول", style=discord.ButtonStyle.green, custom_id="login_btn", emoji="🟢")
    async def login(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        
        # فحص ما إذا كان مسجلاً للدخول بالفعل
        if user.id in database and database[user.id].get("logged_in"):
            await interaction.response.send_message("❌ أنت مسجل دخول بالفعل!", ephemeral=True)
            return

        # الشرط يعتمد فقط على تواجد العضو في الروم الصوتي
        if not user.voice or not user.voice.channel:
            await interaction.response.send_message("❌ يجب أن تكون متواجدًا في الرومات الصوتية لتسجيل الدخول!", ephemeral=True)
            return

        if user.id not in database:
            database[user.id] = {
                "hours": 0.0, 
                "logged_in": False, 
                "afk": False, 
                "login_time": datetime.datetime.now(),
                "warning_type": None,
                "warning_since": None
            }
        
        database[user.id]["logged_in"] = True
        database[user.id]["login_time"] = datetime.datetime.now()
        database[user.id]["afk"] = False
        database[user.id]["warning_type"] = None
        database[user.id]["warning_since"] = None

        # إلغاء أي مهلة سابقة إن وجدت
        if user.id in warning_tasks:
            warning_tasks[user.id].cancel()
            del warning_tasks[user.id]

        embed = discord.Embed(title="طلب تسجيل دخول", color=discord.Color.green())
        embed.add_field(name="الشخص", value=user.mention, inline=False)
        embed.add_field(name="الرومات الصوتية :", value="🟢", inline=True)
        embed.add_field(name="حالة الطلب :", value="مقبول بنجاح ✅", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="تسجيل خروج", style=discord.ButtonStyle.red, custom_id="logout_btn", emoji="🔴")
    async def logout(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in database and database[user_id]["logged_in"]:
            data = database[user_id]
            delta = datetime.datetime.now() - data["login_time"]
            hours_passed = delta.total_seconds() / 3600
            data["hours"] += hours_passed
            data["logged_in"] = False
            data["afk"] = False
            data["warning_type"] = None
            data["warning_since"] = None
            
            if user_id in warning_tasks:
                warning_tasks[user_id].cancel()
                del warning_tasks[user_id]

            await interaction.response.send_message("✅ تم تسجيل خروجك بنجاح وحفظ ساعاتك.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ أنت لست مسجل دخول أساساً!", ephemeral=True)

    @discord.ui.button(label="رجوع/AFK", style=discord.ButtonStyle.blurple, custom_id="afk_btn", emoji="⚠️")
    async def afk_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in database and database[user_id]["logged_in"]:
            database[user_id]["afk"] = not database[user_id]["afk"]
            status = "في وضع AFK الآن" if database[user_id]["afk"] else "تم العودة من الـ AFK"
            await interaction.response.send_message(f"⚠️ {status}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ يجب أن تكون مسجل دخول لتفعيل الـ AFK.", ephemeral=True)

    @discord.ui.button(label="ساعاتي", style=discord.ButtonStyle.gray, custom_id="my_hours_btn", emoji="📸")
    async def my_hours(self, interaction: discord.Interaction, button: discord.ui.Button):
        has_role = any(role.id in ALLOWED_HOURS_ROLES for role in interaction.user.roles)
        if not has_role:
            await interaction.response.send_message("❌ ليس لديك الصلاحية لاستخدام زر ساعاتك.", ephemeral=True)
            return

        user_id = interaction.user.id
        current_hours = database.get(user_id, {}).get("hours", 0.0)
        
        if user_id in database and database[user_id]["logged_in"] and not database[user_id]["afk"]:
            delta = datetime.datetime.now() - database[user_id]["login_time"]
            current_hours += delta.total_seconds() / 3600

        await interaction.response.send_message(f"⏳ إجمالي ساعاتك الإدارية هو: **{current_hours:.2f}** ساعة.", ephemeral=True)

    @discord.ui.button(label="المتواجدين", style=discord.ButtonStyle.blurple, custom_id="online_members_btn", emoji="🟢")
    async def online_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        has_role = any(role.id in ALLOWED_ONLINE_ROLES for role in interaction.user.roles)
        if not has_role:
            await interaction.response.send_message("❌ ليس لديك الصلاحية لعرض المتواجدين.", ephemeral=True)
            return

        active_users = [f"<@{uid}>" for uid, data in database.items() if data.get("logged_in")]
        
        if not active_users:
            await interaction.response.send_message("📭 لا يوجد أي إداري مسجل دخول حالياً.", ephemeral=True)
        else:
            embed = discord.Embed(title="الإداريون المتواجدون حالياً", description="\n".join(active_users), color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def handle_timeout(member):
    import asyncio
    try:
        await asyncio.sleep(600)  # انتظار 10 دقائق
        user_id = member.id
        if user_id in database and database[user_id]["logged_in"]:
            data = database[user_id]
            delta = datetime.datetime.now() - data["login_time"]
            hours_passed = delta.total_seconds() / 3600
            data["hours"] += hours_passed
            data["logged_in"] = False
            data["afk"] = False
            data["warning_type"] = None
            data["warning_since"] = None
            
            total_hours = int(hours_passed)
            total_mins = int((hours_passed - total_hours) * 60)
            
            embed = discord.Embed(
                title="تم إنهاء جلستك",
                description="❌ تم إنهاء جلستك تلقائياً بسبب عدم العودة خلال المهلة المحددّة.",
                color=discord.Color.red()
            )
            embed.add_field(name="المفقود", value="الرومات الصوتية", inline=False)
            embed.add_field(name="المدة المحتسبة", value=f"{total_hours} ساعة و {total_mins} دقيقة", inline=False)
            embed.set_footer(text=f"الوقت والتاريخ: {datetime.datetime.now().strftime('%H:%M %Y/%m/%d')}")
            await member.send(embed=embed)
    except asyncio.CancelledError:
        pass
    finally:
        if member.id in warning_tasks:
            del warning_tasks[member.id]

@bot.event
async def on_voice_state_update(member, before, after):
    user_id = member.id
    if user_id not in database or not database[user_id]["logged_in"]:
        return

    now = datetime.datetime.now()
    was_in_voice = before.channel is not None
    is_in_voice = after.channel is not None

    if was_in_voice and not is_in_voice:
        database[user_id]["warning_type"] = "الرومات الصوتية"
        database[user_id]["warning_since"] = now
        
        try:
            embed = discord.Embed(
                title="تنبيه تسجيل الدخول",
                description="🕹️ تم رصـد خروجك من الرومات الصوتية. لديك 10 دقائق للعودة قبل إلغاء تسجيل الدخول.",
                color=discord.Color.dark_theme()
            )
            embed.add_field(name="المفقود", value="الرومات الصوتية", inline=False)
            embed.add_field(name="المهلة", value="10 دقائق", inline=False)
            embed.set_footer(text=f"الوقت والتاريخ: {now.strftime('%H:%M %Y/%m/%d')}")
            await member.send(embed=embed)
        except:
            pass

        if user_id in warning_tasks:
            warning_tasks[user_id].cancel()
        import asyncio
        warning_tasks[user_id] = asyncio.create_task(handle_timeout(member))

    elif not was_in_voice and is_in_voice:
        if database[user_id]["warning_type"] is not None:
            database[user_id]["warning_type"] = None
            database[user_id]["warning_since"] = None
            
            if user_id in warning_tasks:
                warning_tasks[user_id].cancel()
                del warning_tasks[user_id]
            
            try:
                await member.send("✅ تم رصد عودتك واستئناف شروط تسجيل الدخول بنجاح.")
            except:
                pass

@bot.event
async def on_ready():
    bot.add_view(AdminPanelView())
    print(f"Logged in as {bot.user.name}")
    
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🛠️ آلية التحضير للإدارة العليا",
            description="اختر الإجراء المناسب من الأزرار بالأسفل 👇\n\n"
                        "━━━━━━━━━━━━━━━\n"
                        "🔹 **تسجيل دخول**\n يشترط أن تكون متواجدًا في الرومات الصوتية فقط\n\n"
                        "🔸 **تسجيل خروج**\n لتسجيل خروجك من الإدارة\n\n"
                        "⚠️ **AFK**\n لأخذ وقت مستقطع والحد الأقصى للمدة هي 15 دقيقة\n\n"
                        "━━━━━━━━━━━━━━━",
            color=discord.Color.dark_theme()
        )
        await channel.send(embed=embed, view=AdminPanelView())

@bot.command(name="إضافة")
async def add_hours(ctx, member: discord.Member, hours: float):
    if not any(role.id in OWNER_ROLES for role in ctx.author.roles):
        await ctx.send("❌ ليس لديك صلاحية الأونر لاستخدام هذا الأمر.")
        return
    
    if member.id not in database:
        database[member.id] = {"hours": 0.0, "logged_in": False, "afk": False, "login_time": None, "warning_type": None, "warning_since": None}
    
    database[member.id]["hours"] += hours
    await ctx.send(f"✅ تم إضافة {hours} ساعة لـ {member.mention}. الإجمالي الجديد: {database[member.id]['hours']:.2f}")

@bot.command(name="إزالة")
async def remove_hours(ctx, member: discord.Member, hours: float):
    if not any(role.id in OWNER_ROLES for role in ctx.author.roles):
        await ctx.send("❌ ليس لديك صلاحية الأونر لاستخدام هذا الأمر.")
        return
    
    if member.id in database:
        database[member.id]["hours"] = max(0.0, database[member.id]["hours"] - hours)
        await ctx.send(f"✅ تم خصم {hours} ساعة من {member.mention}. الباقي: {database[member.id]['hours']:.2f}")
    else:
        database[member.id] = {"hours": 0.0, "logged_in": False, "afk": False, "login_time": None, "warning_type": None, "warning_since": None}
        await ctx.send("❌ هذا العضو لم يكن لديه سجل ساعات سابق، تم ضبط رصيده على 0.")

@bot.command(name="إلغاء")
async def cancel_login(ctx, member: discord.Member):
    if not any(role.id in OWNER_ROLES for role in ctx.author.roles):
        await ctx.send("❌ ليس لديك صلاحية الأونر لاستخدام هذا الأمر.")
        return
    
    if member.id in database and database[member.id]["logged_in"]:
        database[member.id]["logged_in"] = False
        database[member.id]["afk"] = False
        database[member.id]["warning_type"] = None
        database[member.id]["warning_since"] = None
        if member.id in warning_tasks:
            warning_tasks[member.id].cancel()
            del warning_tasks[member.id]
        await ctx.send(f"✅ تم إلغاء تسجيل دخول {member.mention} إجبارياً.")
    else:
        await ctx.send("❌ العضو غير مسجل دخول أساساً.")

bot.run("MTU0NzA2NDE1MDkyMzAyMjM3Ng.GwMhKV.JMsr-iPhFqGGkebgw2zyFR8MVDQBBXH0HNn7yQ")