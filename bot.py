BOT_TOKEN = "8645108254:AAG2xvLWF8AaNS4m7-mMK9yDo4gnIKP8GDY" #
ADMIN_ID = 6985111317 #
GROUP_CHAT_ID = -1001826354782 #
from aiohttp import web

async def handle(request):
    return web.Response(text="Bot is Active!")

# Bot ishga tushganda fon rejimida kichik veb-sayt ham ochiladi
app = web.Application()
app.router.add_get('/', handle)

async def start_web_server():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()
