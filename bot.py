import os
import json
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
from datetime import datetime, date
from zoneinfo import ZoneInfo

# ====== CONFIGURAÇÕES ======
TIMEZONE = ZoneInfo("America/Recife")
DATA_FILE = "dados_financeiros.json"
TOKEN = os.getenv("TOKEN")
# ============================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== Funções auxiliares ======
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(user_id):
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = {"saldo": 0.0, "transacoes": []}
        save_data(data)
    return data

def update_user(user_id, registro):
    data = load_data()
    data[str(user_id)] = registro
    save_data(data)

def fmt_money(v):
    return f"R${v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def now():
    return datetime.now(tz=TIMEZONE)

# ====== BOT READY ======
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot conectado como {bot.user}")

# ====== COMANDOS ======
@bot.tree.command(name="add_saldo", description="Adiciona ou define seu saldo total.")
async def add_saldo(interaction: discord.Interaction, valor: float):
    user_id = interaction.user.id
    data = get_user(user_id)
    data[str(user_id)]["saldo"] = valor
    data[str(user_id)]["transacoes"].append({
        "tipo": "definido",
        "valor": valor,
        "motivo": "Saldo inicial definido",
        "hora": now().isoformat()
    })
    save_data(data)
    await interaction.response.send_message(f"💰 Seu saldo foi definido para **{fmt_money(valor)}**.")

@bot.tree.command(name="saldo_atual", description="Mostra seu saldo atual.")
async def saldo_atual(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = get_user(user_id)
    saldo = data[str(user_id)]["saldo"]
    await interaction.response.send_message(f"💵 Seu saldo atual é **{fmt_money(saldo)}**.")

@bot.tree.command(name="gasto", description="Registra um gasto e subtrai do saldo.")
async def gasto(interaction: discord.Interaction, valor: float, motivo: str):
    user_id = interaction.user.id
    data = get_user(user_id)
    data[str(user_id)]["saldo"] -= valor
    data[str(user_id)]["transacoes"].append({
        "tipo": "gasto",
        "valor": valor,
        "motivo": motivo,
        "hora": now().isoformat()
    })
    save_data(data)
    await interaction.response.send_message(f"📉 Gasto de **{fmt_money(valor)}** com **{motivo}** registrado.\nNovo saldo: **{fmt_money(data[str(user_id)]['saldo'])}**.")

@bot.tree.command(name="ganho", description="Registra um ganho e soma ao saldo.")
async def ganho(interaction: discord.Interaction, valor: float, motivo: str):
    user_id = interaction.user.id
    data = get_user(user_id)
    data[str(user_id)]["saldo"] += valor
    data[str(user_id)]["transacoes"].append({
        "tipo": "ganho",
        "valor": valor,
        "motivo": motivo,
        "hora": now().isoformat()
    })
    save_data(data)
    await interaction.response.send_message(f"📈 Ganho de **{fmt_money(valor)}** com **{motivo}** registrado.\nNovo saldo: **{fmt_money(data[str(user_id)]['saldo'])}**.")

# ====== HISTÓRICO COM BOTÕES ======
class HistoricoView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    async def send_embed(self, interaction, tipo):
        data = get_user(self.user_id)
        transacoes = data[str(self.user_id)]["transacoes"]

        hoje = date.today()
        agora = now()
        linhas = []

        for t in transacoes:
            dt = datetime.fromisoformat(t["hora"]).astimezone(TIMEZONE)
            incluir = False

            if tipo == "diario":
                incluir = dt.date() == hoje
            elif tipo == "mensal":
                incluir = (dt.year == hoje.year and dt.month == hoje.month)
            elif tipo == "total":
                incluir = True

            if incluir:
                emoji = "💰" if t["tipo"] == "ganho" else "💸" if t["tipo"] == "gasto" else "⚙️"
                linhas.append(f"[{dt.strftime('%d/%m %H:%M')}] {emoji} {t['tipo'].capitalize()} {fmt_money(t['valor'])} — {t['motivo']}")

        if not linhas:
            linhas = ["Nenhuma transação registrada nesse período."]

        embed = discord.Embed(
            title=f"📜 Histórico {tipo.capitalize()}",
            description="\n".join(linhas[-20:]),
            color=discord.Color.gold()
        )
        embed.add_field(name="💵 Saldo atual", value=fmt_money(data[str(self.user_id)]["saldo"]), inline=False)
        embed.set_footer(text=f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📅 Diário", style=discord.ButtonStyle.primary)
    async def diario(self, interaction: discord.Interaction, button: Button):
        await self.send_embed(interaction, "diario")

    @discord.ui.button(label="🗓️ Mensal", style=discord.ButtonStyle.secondary)
    async def mensal(self, interaction: discord.Interaction, button: Button):
        await self.send_embed(interaction, "mensal")

    @discord.ui.button(label="📊 Total", style=discord.ButtonStyle.success)
    async def total(self, interaction: discord.Interaction, button: Button):
        await self.send_embed(interaction, "total")

@bot.tree.command(name="historico", description="Mostra seu histórico (diário, mensal e total).")
async def historico(interaction: discord.Interaction):
    view = HistoricoView(interaction.user.id)
    await interaction.response.send_message("Escolha qual histórico deseja ver:", view=view)

# ====== RESETAR ======
@bot.tree.command(name="resetar", description="Reseta seu saldo e histórico.")
async def resetar(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = load_data()
    data[str(user_id)] = {"saldo": 0.0, "transacoes": []}
    save_data(data)
    await interaction.response.send_message("🔄 Todos os seus dados foram resetados com sucesso.")

bot.run(MTQyNDY1ODE1NDExMjk0MjE0MA.GyoG2w.Phdq0z6BE4aplaykIhpM73ETbkOq1IEWDTvSc8)
