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
            return await interaction.response.send_message("📋 Nenhum horário cadastrado.", ephemeral=True)
        msg = "📅 **Horários configurados:**\n"
        for h, info in sorted(horarios.items()):
            user = f"<@{info['responsavel']}>" if info["responsavel"] else "N/A"
            msg += f"\n🕐 `{h}` | 🌐 `{info['fuso']}` | 👤 {user}"
        await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="ponto", description="Adiciona 1 ponto ao usuário com motivo.")
@app_commands.describe(usuario="Usuário a ser advertido", motivo="Motivo da advertência")
async def ponto(interaction: discord.Interaction, usuario: discord.User, motivo: str):
    if not somente_dono_slash(interaction):
        return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)

    pontos[str(usuario.id)] = pontos.get(str(usuario.id), 0) + 1
    salvar_json(ARQUIVO_PONTOS, pontos)

    # Enviar DM para o usuário
    try:
        await usuario.send(f"**Você acabou de receber uma advertência na equipe por: {motivo}**")
    except Exception:
        # Caso não possa enviar DM (DMs bloqueadas), apenas ignore
        pass

    # Resposta pública (ou ephemereal)
    if pontos[str(usuario.id)] >= 3:
        await interaction.response.send_message(f"**{usuario.mention} atingiu 3 pontos de advertência.**", ephemeral=False)
    else:
        await interaction.response.send_message(f"**{usuario.mention} agora tem {pontos[str(usuario.id)]} ponto(s).**", ephemeral=True)

@bot.tree.command(name="removeponto", description="Remove 1 ponto do usuário.")
@app_commands.describe(usuario="Usuário a remover ponto")
async def removeponto(interaction: discord.Interaction, usuario: discord.User):
        if not somente_dono_slash(interaction):
            return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        if str(usuario.id) in pontos and pontos[str(usuario.id)] > 0:
            pontos[str(usuario.id)] -= 1
            salvar_json(ARQUIVO_PONTOS, pontos)
            await interaction.response.send_message(f"**{usuario.mention} agora tem {pontos[str(usuario.id)]} ponto(s).**", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Este usuário não possui pontos.", ephemeral=True)

@bot.tree.command(name="verpontos", description="Mostra os pontos de um usuário.")
@app_commands.describe(usuario="Usuário a verificar")
async def verpontos(interaction: discord.Interaction, usuario: discord.User):
        if not somente_dono_slash(interaction):
            return await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        pontos_usuario = pontos.get(str(usuario.id), 0)
        await interaction.response.send_message(f"**{usuario.mention} tem {pontos_usuario} ponto(s).**", ephemeral=True)

    # ------ COMANDOS PREFIXADOS ------ #
@bot.command()
@somente_dono_prefix()
async def backup_roles(ctx):
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

        global roles_backup
        roles_backup = roles_info
        await ctx.send(f"Backup de {len(roles_info)} cargos realizado com sucesso!")

@bot.command()
@somente_dono_prefix()
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

    # -------- NOVO COMANDO: COPIAR PERMISSÕES DOS CANAIS -------- #
@bot.command()
@somente_dono_prefix()
async def copiar_completo(ctx):
        origem = bot.get_guild(ORIGEM_ID)
        destino = bot.get_guild(DESTINO_ID)

        if not origem:
            await ctx.send("Servidor de origem não encontrado.")
            return
        if not destino:
            await ctx.send("Servidor de destino não encontrado.")
            return

        # Dicionário para pegar roles do destino pelo nome
        destino_roles = {role.name: role for role in destino.roles}

        count = 0
        for canal_origem in origem.channels:
            if not isinstance(canal_origem, (discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel)):
                continue
            canal_destino = discord.utils.get(destino.channels, name=canal_origem.name, type=canal_origem.type)
            if not canal_destino:
                continue

            # Montar novo overwrites baseado nos cargos do destino, pelo nome, com as mesmas permissões do canal origem
            novos_overwrites = {}
            for role_origem, overwrite in canal_origem.overwrites.items():
                if isinstance(role_origem, discord.Role):
                    role_destino = destino_roles.get(role_origem.name)
                    if role_destino:
                        novos_overwrites[role_destino] = overwrite

            # Editar canal destino com os overwrites novos
            try:
                await canal_destino.edit(overwrites=novos_overwrites)
                count += 1
            except Exception as e:
                await ctx.send(f"Erro ao editar canal `{canal_destino.name}`: {e}")

        await ctx.send(f"Permissões copiadas para {count} canais do servidor destino.")

    # ------ VERIFICAÇÃO DE STATUS ------ #
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

    # ------ EVENTOS ------ #
@bot.event
async def on_ready():
        try:
            synced = await bot.tree.sync()
            print(f"Slash commands sincronizados: {len(synced)}")
        except Exception as e:
            print(f"Erro na sincronização: {e}")
        checar_horarios.start()
        print(f"Bot online! Logado como {bot.user}.")

bot.run(TOKEN)