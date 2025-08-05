import os
import discord
from flask import Flask
from discord.ext import commands
import threading
from typing import List, Dict

# ------ CONFIGURAÇÕES ------ #
TOKEN = os.getenv("TOKEN")
ORIGEM_ID = 1395784646884855963  # ID do servidor de origem (recuperação)
DESTINO_ID = 1402064209176695035  # ID do servidor de destino (novo)

# IDs dos cargos que não devem ser copiados
CARGOS_EXCLUIDOS = {
    1395784646884855963, 1395784646884855964, 1395785544339820607, 1395785854424977451, 1395786050223345727, 1395784647484375208, 1395784647484375209, 1395784647560138834, 1395784647560138835, 1395784647560138836
}

# Variável global para armazenar backup dos cargos
roles_backup: List[Dict] = []

# ------ FLASK PARA UPTIME ROBOT ------ #
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot online!"

threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 8080}).start()

# ------ INTENTS E BOT ------ #
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ------ COMANDOS ------ #
@bot.command()
async def backup_roles(ctx):
    global roles_backup
    origem = bot.get_guild(ORIGEM_ID)
    if not origem:
        await ctx.send("Servidor de origem não encontrado.")
        return

    roles_info = []
    for role in origem.roles:
        if role.name != "@everyone" and role.id not in CARGOS_EXCLUIDOS:
            roles_info.append({
                "id": role.id,
                "name": role.name,
                "permissions": role.permissions.value,
                "color": role.color.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "position": role.position
            })

    roles_backup = roles_info
    await ctx.send(f"Backup de {len(roles_info)} cargos realizado com sucesso!")

@bot.command()
async def restaurar_roles(ctx):
    destino = bot.get_guild(DESTINO_ID)
    if not destino:
        await ctx.send("Servidor de destino não encontrado.")
        return

    if not roles_backup:
        await ctx.send("Nenhum backup encontrado. Use !backup_roles primeiro.")
        return

    # Ordem invertida para criar cargos do topo para baixo (posição maior primeiro)
    for role_info in sorted(roles_backup, key=lambda x: x["position"], reverse=True):
        await destino.create_role(
            name=role_info["name"],
            permissions=discord.Permissions(role_info["permissions"]),
            color=discord.Color(role_info["color"]),
            hoist=role_info["hoist"],
            mentionable=role_info["mentionable"]
        )

    await ctx.send(f"Restauração de {len(roles_backup)} cargos concluída com sucesso!")

# ------ EVENTO READY ------ #
@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

# ------ EXECUÇÃO ------ #
if TOKEN is None:
    print("❌ TOKEN não definido na variável de ambiente.")
else:
    bot.run(TOKEN)