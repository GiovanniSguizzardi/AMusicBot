import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

# Intents necessários
intents = discord.Intents.default()
intents.message_content = True  # Necessário para ler mensagens

# Dicionário para armazenar prefixos por servidor
prefixos = {}

# Função para obter o prefixo dinamicamente por servidor
def get_prefix(bot, message):
    return prefixos.get(message.guild.id, '!')  # O prefixo padrão é '!'

# Inicializar o bot com a função de obter prefixo dinamicamente
bot = commands.Bot(command_prefix=get_prefix, intents=intents)

# Variáveis globais
song_queue = []  # Fila de músicas
looping = False  # Controle de loop

# Remover mensagens de aviso do yt-dlp
youtube_dl.utils.bug_reports_message = lambda: ''

# Configurações do yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # Define o endereço IP de origem
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',  # Reconectar caso ocorra algum erro
    'options': '-vn'  # Excluir vídeo da reprodução
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            print(f'[ERRO] Falha ao extrair informações do áudio: {e}')
            return None

        if 'entries' in data:
            # Obtém a primeira música da lista de reprodução (caso haja uma)
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print('')
    print(f'--> AMusicBOT está online! - (VERSÃO 0.0.1)')
    print('')

# Função para tocar a próxima música da fila
async def play_next(ctx):
    if len(song_queue) > 0:
        # Toca a próxima música
        next_song = song_queue.pop(0)
        player = await YTDLSource.from_url(next_song, loop=bot.loop, stream=True)
        ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))

        embed = discord.Embed(title="Tocando Próxima Música", description=f"Tocando agora: {player.title}", color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        await ctx.send("[INFO] A fila de músicas está vazia.")

# Comando para tocar música e adicionar à fila
@bot.command(name='play', help='Toca uma música a partir de um link do YouTube ou uma pesquisa')
async def play(ctx, *, url):
    global looping
    if not ctx.author.voice:
        embed = discord.Embed(title="Erro", description="Você precisa estar em um canal de voz para usar este comando.", color=discord.Color.red())
        await ctx.send(embed=embed)
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        
        if player is None:
            embed = discord.Embed(title="Erro", description="Não foi possível processar o áudio do link fornecido.", color=discord.Color.red())
            await ctx.send(embed=embed)
            return
        
        if ctx.voice_client.is_playing():
            song_queue.append(url)  # Adiciona à fila se já houver uma música tocando
            embed = discord.Embed(title="Adicionada à Fila", description=f"Música: {player.title}", color=discord.Color.blue())
            await ctx.send(embed=embed)
        else:
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
            embed = discord.Embed(title="Tocando Música", description=f"Tocando agora: {player.title}", color=discord.Color.green())
            await ctx.send(embed=embed)

# Comando para exibir a lista de músicas
@bot.command(name='lista', help='Exibe a lista de reprodução')
async def lista(ctx):
    if len(song_queue) == 0:
        embed = discord.Embed(title="Fila de Músicas", description="A fila está vazia.", color=discord.Color.orange())
    else:
        description = "\n".join([f"{idx + 1}. {url}" for idx, url in enumerate(song_queue)])
        embed = discord.Embed(title="Fila de Músicas", description=description, color=discord.Color.blue())
    
    await ctx.send(embed=embed)

# Comando para pausar a música
@bot.command(name='pause', help='Pausa a música atual')
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        embed = discord.Embed(title="Pausado", description="A música foi pausada.", color=discord.Color.orange())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="Erro", description="Nenhuma música está tocando no momento.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para retomar a música pausada
@bot.command(name='resume', help='Retoma a música pausada')
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        embed = discord.Embed(title="Retomado", description="A música foi retomada.", color=discord.Color.green())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="Erro", description="Nenhuma música está pausada.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para pular a música atual
@bot.command(name='skip', help='Pula a música atual')
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        embed = discord.Embed(title="Pulado", description="A música foi pulada.", color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="Erro", description="Nenhuma música está tocando para pular.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para loop da música
@bot.command(name='loop', help='Ativa ou desativa o loop da música atual')
async def loop(ctx):
    global looping
    looping = not looping  # Inverte o estado do loop

    if looping:
        embed = discord.Embed(title="Loop Ativado", description="O loop foi ativado. A música atual será repetida.", color=discord.Color.purple())
    else:
        embed = discord.Embed(title="Loop Desativado", description="O loop foi desativado.", color=discord.Color.purple())

    await ctx.send(embed=embed)

# Comando para parar a música e desconectar o bot
@bot.command(name='stop', help='Para a música atual e desconecta o bot')
async def stop(ctx):
    global looping
    looping = False  # Desativa o loop ao parar
    song_queue.clear()  # Limpa a fila de músicas

    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        embed = discord.Embed(title="Desconectado", description="O bot foi desconectado do canal de voz.", color=discord.Color.red())
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(title="Erro", description="O bot não está conectado a nenhum canal de voz.", color=discord.Color.red())
        await ctx.send(embed=embed)

# Comando para mudar o prefixo
@bot.command(name='prefixo', help='Muda o prefixo dos comandos do bot')
async def mudar_prefixo(ctx, novo_prefixo: str):
    prefixos[ctx.guild.id] = novo_prefixo
    embed = discord.Embed(title="Prefixo Alterado", description=f"O novo prefixo é `{novo_prefixo}`", color=discord.Color.green())
    await ctx.send(embed=embed)

# Comando para exibir os comandos disponíveis
@bot.command(name='comandos', help='Exibe todos os comandos disponíveis')
async def comandos(ctx):
    prefix = prefixos.get(ctx.guild.id, '!')
    embed = discord.Embed(title="Lista de Comandos", description="Aqui estão todos os comandos disponíveis:", color=discord.Color.blue())
    
    embed.add_field(name=f"{prefix}play [url]", value="Toca uma música do YouTube.", inline=False)
    embed.add_field(name=f"{prefix}lista", value="Mostra a fila de músicas.", inline=False)
    embed.add_field(name=f"{prefix}pause", value="Pausa a música atual.", inline=False)
    embed.add_field(name=f"{prefix}resume", value="Retoma a música pausada.", inline=False)
    embed.add_field(name=f"{prefix}skip", value="Pula a música atual.", inline=False)
    embed.add_field(name=f"{prefix}loop", value="Ativa ou desativa o loop da música atual.", inline=False)
    embed.add_field(name=f"{prefix}stop", value="Para a música e desconecta o bot.", inline=False)
    embed.add_field(name=f"{prefix}prefixo [novo_prefixo]", value="Muda o prefixo dos comandos do bot.", inline=False)
    await ctx.send(embed=embed)

TOKEN = os.getenv('DISCORD_TOKEN')
bot.run(TOKEN)
