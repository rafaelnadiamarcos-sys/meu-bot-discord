import os
import json
import discord
import pytz
from flask import Flask
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import threading
from typing import List, Dict

# ------ CONFIGURAÇÕES ------ #
CANAL_AVISO_ID = 1401207342913032383
CANAL_JUSTIFICATIVA_ID = 1400991354099863572
CANAL_STATUS_FAC_ID = 1370899635618582700
CANAL_STATUS_CORP_ID = 1370899580929052682
ARQUIVO_HORARIOS = "horarios.json"
ARQUIVO_PONTOS = "pontos.json"
DONO_ID = 1369407083623223469
TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    raise ValueError("Variável de ambiente TOKEN não definida.")

ORIGEM_ID = 1395784646884855963  # ID do servidor de origem (recuperação)
DESTINO_ID = 1273079912223342685  # ID do servidor de destino (novo)

CARGOS_EXCLUIDOS = {
    1395784646884855963, 1395784646884855964, 1395785544339820607, 1395785854424977451,
    1395786050223345727, 1395784647484375208, 1395784647484375209, 1395784647560138834,
    1395784647560138835, 1395784647560138836
}

roles_backup: List[Dict] = []

# ------ FLASK PARA UPTIME ROBOT ------ #
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot online!"

threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": 8080}).start()

# ------ INTENTS E BOT ------ #
intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ------ CHECKS DE PERMISSÃO ------ #
def somente_dono_slash(interaction: discord.Interaction):
    return interaction.user.id == DONO_ID

def somente_dono_prefix():
    async def predicate(ctx):
        return ctx.author.id == DONO_ID
    return commands.check(predicate)

# ------ FUNÇÕES AUXILIARES ------ #
def carregar_json(caminho):
    if os.path.exists(caminho):
        with open(caminho, "r") as f:
            return json.load(f)
    return {}

def salvar_json(caminho, data):
    with open(caminho, "w") as f:
        json.dump(data, f, indent=4)

horarios = carregar_json(ARQUIVO_HORARIOS)
pontos = carregar_json(ARQUIVO_PONTOS)
pending_checks = {}

# ------ COMANDOS SLASH ------ #

@bot.tree.command(name="addhorario", description="Adiciona um novo horário.")
@app_commands.describe(horario="Formato HH:MM", fuso="Ex: America/Sao_Paulo")
async def addhorario(interaction: discord.Interaction, horario: str, fuso: str):
    if not somente_dono_slash(interaction):
        return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
    try:
        datetime.strptime(horario, "%H:%M")
        pytz.timezone(fuso)
    except Exception:
        return await interaction.response.send_message("❌ Horário ou fuso inválido.", ephemeral=True)
    if horario in horarios:
        return await interaction.response.send_message("❌ Horário já existe.", ephemeral=True)
    horarios[horario] = {"responsavel": None, "fuso": fuso}
    salvar_json(ARQUIVO_HORARIOS, horarios)
    await interaction.response.send_message(f"✅ Horário `{horario}` adicionado com fuso `{fuso}`.", ephemeral=True)

@bot.tree.command(name="confighorario", description="Atribui um usuário a um horário existente.")
@app_commands.describe(usuario="Usuário para atribuir", horario="Horário no formato HH:MM")
async def confighorario(interaction: discord.Interaction, usuario: discord.User, horario: str):
    if not somente_dono_slash(interaction):
        return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
    horario = horario.strip()
    if horario not in horarios:
        return await interaction.response.send_message(f"❌ O horário `{horario}` não foi encontrado.", ephemeral=True)
    horarios[horario]["responsavel"] = usuario.id
    salvar_json(ARQUIVO_HORARIOS, horarios)
    await interaction.response.send_message(f"✅ {usuario.mention} atribuído ao horário `{horario}`.", ephemeral=True)

@bot.tree.command(name="removehorario", description="Remove um horário.")
@app_commands.describe(horario="Horário no formato HH:MM")
async def removehorario(interaction: discord.Interaction, horario: str):
    if not somente_dono_slash(interaction):
        return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
    if horario in horarios:
        horarios.pop(horario)
        salvar_json(ARQUIVO_HORARIOS, horarios)
        await interaction.response.send_message(f"✅ Horário `{horario}` removido.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Horário não encontrado.", ephemeral=True)

@bot.tree.command(name="verhorarios", description="Lista os horários configurados.")
async def verhorarios(interaction: discord.Interaction):
    if not somente_dono_slash(interaction):
        return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
    if not horarios:
        return await interaction.response.send_message("Nenhum horário configurado.", ephemeral=True)
    msg = ""
    for h, dados in horarios.items():
        resp = f"<@{dados['responsavel']}>" if dados['responsavel'] else "Nenhum"
        msg += f"**{h} ({dados['fuso']}):** {resp}\n"
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="ponto", description="Adiciona um ponto a um usuário.")
@app_commands.describe(usuario="Mencione o usuário", motivo="Motivo da advertência")
async def ponto(interaction: discord.Interaction, usuario: discord.User, motivo: str):
    if not somente_dono_slash(interaction):
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    user_id = str(usuario.id)

    # Corrige estrutura antiga (int) para nova (lista)
    if isinstance(pontos.get(user_id), int):
        pontos[user_id] = [f"Ponto antigo {i+1}" for i in range(pontos[user_id])]

    if user_id not in pontos:
        pontos[user_id] = []

    pontos[user_id].append(motivo)
    salvar_json(ARQUIVO_PONTOS, pontos)

    try:
        await usuario.send(
            f"**Você acabou de receber uma advertência.**\n"
            f"Motivo: {motivo}\n"
            f"***Caso queira revogá-la, contate o <@{DONO_ID}>***"
        )
    except (discord.Forbidden, discord.HTTPException):
        await interaction.response.send_message(
            f"⚠️ {usuario.mention} recebeu uma advertência por: **{motivo}**, mas não foi possível enviar DM.",
            ephemeral=False
        )
        return

    await interaction.response.send_message(
        f"✅ {usuario.mention} recebeu uma advertência por: **{motivo}**",
        ephemeral=False
    )

    # Aviso se chegar a 3 pontos
    if len(pontos[user_id]) == 3:
        await interaction.followup.send(
            f"⚠️ {usuario.mention} agora tem 3 advertências!",
            ephemeral=False
        )

@bot.tree.command(name="removerpontos", description="Remove um ponto de um usuário.")
@app_commands.describe(usuario="Usuário", quantidade="Quantidade de pontos a remover")
async def removerpontos(interaction: discord.Interaction, usuario: discord.User, quantidade: int = 1):
    if not somente_dono_slash(interaction):
        return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)

    user_id = str(usuario.id)
    if user_id not in pontos or len(pontos[user_id]) == 0:
        return await interaction.response.send_message(f"❌ {usuario.mention} não possui pontos.", ephemeral=True)

    quantidade = max(1, quantidade)
    pontos[user_id] = pontos[user_id][:-quantidade] if len(pontos[user_id]) >= quantidade else []

    salvar_json(ARQUIVO_PONTOS, pontos)
    await interaction.response.send_message(f"✅ Removidos {quantidade} ponto(s) de {usuario.mention}.", ephemeral=False)

@bot.tree.command(name="removerallpontos", description="Remove todos os pontos de um usuário.")
@app_commands.describe(usuario="Usuário")
async def removerallpontos(interaction: discord.Interaction, usuario: discord.User):
    if not somente_dono_slash(interaction):
        return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)

    user_id = str(usuario.id)
    if user_id not in pontos or len(pontos[user_id]) == 0:
        return await interaction.response.send_message(f"❌ {usuario.mention} não possui pontos.", ephemeral=True)

    pontos[user_id] = []
    salvar_json(ARQUIVO_PONTOS, pontos)
    await interaction.response.send_message(f"✅ Todos os pontos de {usuario.mention} foram removidos.", ephemeral=False)

# ------ EVENTOS ------ #

@bot.event
async def on_ready():
    user = bot.user
    if user:
        print(f"Bot conectado como {user} (ID: {user.id})")
    else:
        print("Bot conectado, mas bot.user ainda é None")
    await bot.tree.sync()
    print("Comandos slash sincronizados.")

# ------ RODAR BOT ------ #
bot.run(TOKEN)