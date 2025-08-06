# Водяной знак программы можно убрать, я нре запрещаю:))
print(r"""
__     __    _              __  __           _                 
\ \   / /__ (_) ___ ___     |  \/  | __ _ ___| |_ _ __ ___ _ __ 
 \ \ / / _ \| |/ __/ _ \    | |\/| |/ _` / __| __| '__/ _ \ '__|
  \ V / (_) | | (_|  __/    | |  | | (_| \__ \ |_| | |  __/ |   
   \_/ \___/|_|\___\___|    |_|  |_|\__,_|___/\__|_|  \___|_|   

               Created by NatanOsant
              Приятного использования!
""")

# То, что будет помечено как "#РЕДАЧЬ" - будет означать что нужно вставить переменные из Discord-а
# Если вы НЕ хотите, можете ничего не  менять, просто в вашем случае надо будет поменять IDE статус бота(игровой)
# И потребуется токен Discord.
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
import asyncio
from datetime import datetime
import traceback

# Конфигурация
TOKEN = '  '                                 #РЕДАЧЬ
LOBBY_CHANNEL_ID =                           #РЕДАЧЬ
ALLOWED_CATEGORY_ID   =                      #РЕДАЧЬ
CHANNEL_PREFIX = "Перед названием канала "   #РЕДАЧЬ
USER_LIMIT = 99
UPDATE_INTERVAL = 1  # секунды между обновлениями

# Настройка бота
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Словари для хранения данных
channel_deletion_tasks = {}
channel_control_messages = {}
active_voice_channels = {}

class ChangeLimitModal(Modal, title="Изменение лимита канала"):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        current_limit = str(channel.user_limit) if channel.user_limit else ""
        self.limit_input = TextInput(
            label="Новый лимит пользователей",
            placeholder=f"Текущий лимит: {current_limit} (0-99)",
            min_length=1,
            max_length=2
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            value = self.limit_input.value.strip()
            if not value.isdigit():
                await interaction.response.send_message(
                    "❌ Пожалуйста, введите число",
                    ephemeral=True
                )
                return
                
            new_limit = int(value)
            if new_limit < 0 or new_limit > 99:
                await interaction.response.send_message(
                    "❌ Лимит должен быть от 0 до 99",
                    ephemeral=True
                )
                return
                
            await self.channel.edit(user_limit=new_limit)
            await interaction.response.send_message(
                f"✅ Лимит канала изменён на {new_limit}",
                ephemeral=True
            )
            await update_control_panel(self.channel)
        except Exception as e:
            print(f"Ошибка в ChangeLimitModal: {e}")
            traceback.print_exc()

class ChangeNameModal(Modal, title="Изменение названия канала"):
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        self.name_input = TextInput(
            label="Новое название канала",
            placeholder=f"Текущее название: {channel.name}",
            min_length=2,
            max_length=100
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_name = self.name_input.value.strip()
            if not new_name:
                await interaction.response.send_message(
                    "❌ Название не может быть пустым",
                    ephemeral=True
                )
                return
                
            if len(new_name) < 2 or len(new_name) > 100:
                await interaction.response.send_message(
                    "❌ Название должно быть от 2 до 100 символов",
                    ephemeral=True
                )
                return
                
            await self.channel.edit(name=new_name)
            await interaction.response.send_message(
                f"✅ Название канала изменено на '{new_name}'",
                ephemeral=True
            )
            await update_control_panel(self.channel)
        except Exception as e:
            print(f"Ошибка в ChangeNameModal: {e}")
            traceback.print_exc()

class ChannelControlView(View):
    def __init__(self, channel):
        super().__init__(timeout=None)
        self.channel = channel
    
    @discord.ui.button(label="Изменить лимит", style=discord.ButtonStyle.primary, custom_id="change_limit")
    async def change_limit_button(self, interaction: discord.Interaction, button: Button):
        try:
            modal = ChangeLimitModal(self.channel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Ошибка в change_limit_button: {e}")
            traceback.print_exc()
    
    @discord.ui.button(label="Изменить название", style=discord.ButtonStyle.secondary, custom_id="change_name")
    async def change_name_button(self, interaction: discord.Interaction, button: Button):
        try:
            modal = ChangeNameModal(self.channel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"Ошибка в change_name_button: {e}")
            traceback.print_exc()

async def create_control_panel(channel, owner):
    """Создает панель управления каналом"""
    try:
        embed = discord.Embed(
            title=f"Управление каналом: {channel.name}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Участники",
            value=f"{len(channel.members)}/{channel.user_limit if channel.user_limit else '∞'}",
            inline=True
        )
        embed.add_field(
            name="Создан",
            value=f"<t:{int(datetime.now().timestamp())}:R>",
            inline=True
        )
        embed.set_footer(text="Обновляется автоматически")
        
        view = ChannelControlView(channel)
        msg = await owner.send(embed=embed, view=view)
        channel_control_messages[channel.id] = msg
        active_voice_channels[channel.id] = channel
        return msg
    except discord.Forbidden:
        print(f"Не удалось отправить ЛС пользователю {owner}")
        return None
    except Exception as e:
        print(f"Ошибка в create_control_panel: {e}")
        traceback.print_exc()
        return None

async def update_control_panel(channel):
    """Обновляет панель управления каналом"""
    try:
        if channel.id not in channel_control_messages:
            return
        
        msg = channel_control_messages.get(channel.id)
        if not msg:
            return
        
        embed = discord.Embed(
            title=f"Управление каналом: {channel.name}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Участники",
            value=f"{len(channel.members)}/{channel.user_limit if channel.user_limit else '∞'}",
            inline=True
        )
        embed.add_field(
            name="Создан",
            value=f"<t:{int(datetime.now().timestamp())}:R>",
            inline=True
        )
        embed.set_footer(text="Обновлено")
        
        view = ChannelControlView(channel)
        await msg.edit(embed=embed, view=view)
    except discord.NotFound:
        print(f"Сообщение управления для канала {channel.id} не найдено")
        if channel.id in channel_control_messages:
            del channel_control_messages[channel.id]
    except Exception as e:
        print(f"Ошибка в update_control_panel: {e}")
        traceback.print_exc()

@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_all_panels():
    """Периодически обновляет все панели управления"""
    try:
        for channel_id in list(active_voice_channels.keys()):
            channel = active_voice_channels.get(channel_id)
            if channel:
                await update_control_panel(channel)
            else:
                del active_voice_channels[channel_id]
    except Exception as e:
        print(f"Ошибка в update_all_panels: {e}")
        traceback.print_exc()

async def delete_channel_after_empty(channel):
    """Удаляет канал после того, как он опустеет"""
    try:
        while len(channel.members) > 0:
            await asyncio.sleep(5)
        
        await asyncio.sleep(5)
        
        if len(channel.members) == 0:
            # Удаляем сообщение управления
            if channel.id in channel_control_messages:
                try:
                    msg = channel_control_messages[channel.id]
                    await msg.delete()
                    print(f"Сообщение управления для канала {channel.name} удалено")
                except:
                    pass
                del channel_control_messages[channel.id]
            
            if channel.id in active_voice_channels:
                del active_voice_channels[channel.id]
            
            await channel.delete()
            print(f"Канал {channel.name} удален (пустой)")
    except discord.NotFound:
        print(f"Канал {channel.name} уже был удален")
    except Exception as e:
        print(f"Ошибка в delete_channel_after_empty: {e}")
        traceback.print_exc()
    finally:
        if channel.id in channel_deletion_tasks:
            del channel_deletion_tasks[channel.id]

@bot.event
async def on_ready():
    try:
        print('\n=== Бот успешно запущен ===')
        print(f'Имя: {bot.user.name}')
        print(f'ID: {bot.user.id}')
        print('============================\n')
        
        # Функция для обновления статуса с текущим пингом 
        #РЕДАЧЬ
        async def update_presence():
            try:
                latency = round(bot.latency * 1000)  # Получаем и округляем пинг
                await bot.change_presence(
                    activity=discord.Game(name=f"тестирование | ЧЕКНИ БИО | Ping: {latency} мс.")
                )
            except:
                await bot.change_presence(
                    activity=discord.Game(name="тестирование | ЧЕКНИ БИО | Ping: ? ms")
                )
        
        # Сначала обновляем статус один раз
        await update_presence()
        
        # Затем запускаем периодическое обновление
        @tasks.loop(seconds=10)
        async def status_updater():
            await update_presence()
        
        status_updater.start()
        
        # Запускаем задачу обновления панелей
        if not update_all_panels.is_running():
            update_all_panels.start()
            
    except Exception as e:
        print(f"Ошибка в on_ready: {e}")
        traceback.print_exc()

@bot.event
async def on_voice_state_update(member, before, after):
    try:
        # Если пользователь подключился к лобби-каналу
        if after.channel and after.channel.id == LOBBY_CHANNEL_ID:
            print(f'\nПользователь {member} зашел в лобби')
            
            guild = after.channel.guild
            category = guild.get_channel(ALLOWED_CATEGORY_ID)
            
            if not category:
                print(f'ОШИБКА: Категория с ID {ALLOWED_CATEGORY_ID} не найдена!')
                return
            
            # Создаем новый канал
            try:
                new_channel = await guild.create_voice_channel(
                    name=f"{CHANNEL_PREFIX}{member.display_name}",
                    category=category,
                    user_limit=USER_LIMIT
                )
                print(f'Создан новый канал: {new_channel.name}')
            except Exception as e:
                print(f'ОШИБКА при создании канала: {e}')
                traceback.print_exc()
                return
            
            # Перемещаем пользователя
            try:
                await member.move_to(new_channel)
                print(f'Пользователь {member} перемещен в {new_channel.name}')
            except Exception as e:
                print(f'ОШИБКА при перемещении: {e}')
                traceback.print_exc()
                await new_channel.delete()
                return
            
            # Устанавливаем mute по умолчанию
            try:
                await new_channel.set_permissions(member, speak=False)
            except Exception as e:
                print(f'ОШИБКА при настройке прав: {e}')
                traceback.print_exc()
            
            # Создаем панель управления
            await create_control_panel(new_channel, member)
            
            # Создаем задачу на удаление канала
            if new_channel.id not in channel_deletion_tasks:
                task = bot.loop.create_task(delete_channel_after_empty(new_channel))
                channel_deletion_tasks[new_channel.id] = task
        
        # Обновляем панели при изменении состояния голосовых каналов
        if before.channel and before.channel.id in active_voice_channels:
            await update_control_panel(before.channel)
        if after.channel and after.channel.id in active_voice_channels:
            await update_control_panel(after.channel)
        
        # Если пользователь вышел из канала в категории (но не из лобби)
        if (before.channel and before.channel.category_id == ALLOWED_CATEGORY_ID 
                and before.channel.id != LOBBY_CHANNEL_ID):
            if len(before.channel.members) == 0:
                if before.channel.id not in channel_deletion_tasks:
                    task = bot.loop.create_task(delete_channel_after_empty(before.channel))
                    channel_deletion_tasks[before.channel.id] = task
    
    except Exception as e:
        print(f'КРИТИЧЕСКАЯ ОШИБКА в on_voice_state_update: {e}')
        traceback.print_exc()

# Обработчик ошибок запуска
try:
    print('Запуск бота...') #РЕДАЧЬ
    bot.run(TOKEN)
except discord.LoginFailure:
    print('\nОШИБКА: Неверный токен бота! Проверьте токен.')
    traceback.print_exc()
except discord.PrivilegedIntentsRequired:
    print('\nОШИБКА: Не включены необходимые привилегированные интенты!')
    print('Зайдите в портал разработчика Discord и включите:')
    print('- SERVER MEMBERS INTENT')
    print('- PRESENCE INTENT')
    traceback.print_exc()
except Exception as e:
    print(f'\nКРИТИЧЕСКАЯ ОШИБКА: {type(e).__name__}: {e}')
    traceback.print_exc()
finally:
    try:
        update_all_panels.cancel()
    except:
        pass
    print('\nРабота бота завершена')