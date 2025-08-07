import os
import json
import discord
import pytz
from flask import Flask
from discord.ext import commands, tasks
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

ORIGEM_ID = 1395784646884855963
DESTINO_ID = 1273079912223342685

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
        return await interaction.response.send_message("📋 Nenhum horário cadastrado.", ephemeral=True)
    msg = "📅 **Horários configurados:**\n"
    for h, info in sorted(horarios.items()):
        user = f"<@{info['responsavel']}>" if info["responsavel"] else "N/A"
        msg += f"\n🕐 `{h}` | 🌐 `{info['fuso']}` | 👤 {user}"
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="ponto", description="Adiciona um ponto a um usuário.")
@app_commands.describe(usuario="Mencione o usuário", motivo="Motivo da advertência")
async def ponto(interaction: discord.Interaction, usuario: discord.User, motivo: str):
    if not somente_dono_slash(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    user_id = str(usuario.id)

    if isinstance(pontos.get(user_id), int):
        pontos[user_id] = [f"Ponto antigo {i+1}" for i in range(pontos[user_id])]
    if user_id not in pontos:
        pontos[user_id] = []

    pontos[user_id].append(motivo)
    salvar_json(ARQUIVO_PONTOS, pontos)

    try:
        await usuario.send(
            f"**Você acabou de receber uma advertência.\nMotivo: {motivo}**\n***Caso queira revoga-la, contate o <@{DONO_ID}>***"
        )
    except (discord.Forbidden, discord.HTTPException):
        await interaction.response.send_message(
            f"⚠️ {usuario.mention} recebeu uma advertência, mas não foi possível enviar DM.",
            ephemeral=False
        )
        return

    await interaction.response.send_message(
        f"✅ {usuario.mention} recebeu uma advertência por: **{motivo}**",
        ephemeral=False
    )

@bot.tree.command(name="verpontos", description="Mostra todos os pontos registrados dos usuários.")
async def verpontos(interaction: discord.Interaction):
    if not somente_dono_slash(interaction):
        return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
    if not pontos:
        return await interaction.response.send_message("📭 Nenhum ponto registrado ainda.", ephemeral=True)

    mensagem = ""
    for user_id, lista_pontos in pontos.items():
        try:
            user = await bot.fetch_user(int(user_id))
            mensagem += f"**{user.mention}**\n"
            for i, motivo in enumerate(lista_pontos, start=1):
                mensagem += f"{i}º ponto: {motivo}\n"
            mensagem += "\n"
        except Exception as e:
            print(f"[Erro] Falha ao buscar usuário {user_id}: {e}")
            continue

    await interaction.response.send_message(mensagem, ephemeral=False)

@bot.tree.command(name="removerponto", description="Remove um ponto específico de um usuário.")
@app_commands.describe(usuario="Usuário", numero="Número do ponto (1, 2, 3...)")
async def removerponto(interaction: discord.Interaction, usuario: discord.User, numero: int):
    if not somente_dono_slash(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    user_id = str(usuario.id)
    if user_id not in pontos or numero < 1 or numero > len(pontos[user_id]):
        await interaction.response.send_message("❌ Ponto não encontrado.", ephemeral=True)
        return

    removido = pontos[user_id].pop(numero - 1)
    if not pontos[user_id]:
        pontos.pop(user_id)

    salvar_json(ARQUIVO_PONTOS, pontos)
    await interaction.response.send_message(f"✅ Ponto removido de {usuario.mention}: **{removido}**", ephemeral=False)

@bot.tree.command(name="removerallpontos", description="Remove todos os pontos de um usuário.")
@app_commands.describe(usuario="Usuário")
async def removerallpontos(interaction: discord.Interaction, usuario: discord.User):
    if not somente_dono_slash(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    user_id = str(usuario.id)
    if user_id not in pontos:
        await interaction.response.send_message("❌ Este usuário não possui pontos.", ephemeral=True)
        return

    pontos.pop(user_id)
    salvar_json(ARQUIVO_PONTOS, pontos)
    await interaction.response.send_message(f"✅ Todos os pontos de {usuario.mention} foram removidos.", ephemeral=False)

# ------ EVENTOS E BACKUP ------ #
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Slash commands sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Erro na sincronização: {e}")
    checar_horarios.start()
    print(f"Bot online! Logado como {bot.user}.")

@tasks.loop(minutes=1)
async def checar_horarios():
    agora_utc = datetime.now(pytz.UTC)
    canal = bot.get_channel(CANAL_AVISO_ID)
    if not isinstance(canal, discord.TextChannel):
        return
    for horario, info in horarios.items():
        try:
            fuso = pytz.timezone(info["fuso"])
            alvo = datetime.strptime(horario, "%H:%M").time()
            local = agora_utc.astimezone(fuso)
            if local.hour == alvo.hour and local.minute == alvo.minute:
                responsavel_id = info.get("responsavel")
                if responsavel_id:
                    membro = await bot.fetch_user(responsavel_id)
                    await canal.send(f"**🔔 {membro.mention}, chegou seu horário de responsabilidade: `{horario}`.**")
                    pending_checks[responsavel_id] = datetime.now()
        except Exception as e:
            print(f"Erro ao checar horário {horario}: {e}")
    for user_id, horario_inicio in list(pending_checks.items()):
        if (datetime.now() - horario_inicio).seconds >= 600:
            membro = await bot.fetch_user(user_id)
            logs = []
            for canal_id in [CANAL_STATUS_FAC_ID, CANAL_STATUS_CORP_ID, CANAL_JUSTIFICATIVA_ID]:
                canal = bot.get_channel(canal_id)
                if isinstance(canal, discord.TextChannel):
                    async for msg in canal.history(limit=50):
                        if msg.author.id == user_id:
                            logs.append(msg)
            if not logs:
                dono = await bot.fetch_user(DONO_ID)
                await dono.send(f"**@{membro} não realizou o Status e não se justificou.**\n**Canal status fac:** <#{CANAL_STATUS_FAC_ID}>\n**Canal status corp:** <#{CANAL_STATUS_CORP_ID}>")
            pending_checks.pop(user_id)

bot.run(TOKEN)