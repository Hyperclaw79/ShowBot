import discord
import inspect
import aiohttp
import requests
import os
import json
import asyncio

cluster = os.environ["CLUSTER_NAME"]
discord_token = os.environ["DISCORD_TOKEN"]

class Response:
    def __init__(self, content, reply=False, delete_after=0):
        self.content = content
        self.reply = reply
        self.delete_after = delete_after

class ShowBot(discord.Client):
    def __init__(self):
        self.prefix = '$'
        super().__init__()
        self.aiosession = aiohttp.ClientSession(loop=self.loop)
        self.http.user_agent += ' ShowBot/1.0'

    async def on_ready(self):
        print('ShowBot is now live!')


    async def cmd_ping(self, message):
        await message.channel.send("Pong!")

    async def cmd_say(self, message):
        msg = message.content.replace("{}say".format(self.prefix),'').strip() 
        await message.channel.send(msg)
        try:
            await message.delete()    
        except:
            print('Jeez! I need better permissions in {}.'.format(message.guild))

    async def cmd_showtimes(self, message):
        def check(msg):
            return msg.author == message.author

        def formatter(dic):
            venue = "Theatre: [{}]".format(dic["Venue"])
            venue = venue+"\n{}".format('-' * int(1.25 * len(venue)))
            shows = dic["Shows"]
            shw = ''
            for show in shows:
                sh = '\n#Show:\t{}\n'.format(show["time"].replace(':','\uFF1A'))
                s = ''
                for category in list(show["categories"].keys()):
                    categ = show["categories"][category]
                    s = s + '\t[{}]:\t{{Available: \'{}\'}}\n\t\t{}{{Price: \'INR {}\'}}\n'.format(category, categ["Seats: "], (' ' * (len(category) + 3)),categ["Price: "]) 
                    sh = sh + s
                shw = shw + sh
            msg = venue + shw
            return msg    

        async def reactor(msg,val):
            def check2(temp,user):
                return user == message.author and temp.message.id == msg.id and temp.emoji in reaction_list

            reaction_list = []
            for num in range(val):
                await msg.add_reaction('{}\u20e3'.format(num+1))
                reaction_list.append('{}\u20e3'.format(num+1))
            temp, user = await self.wait_for('reaction_add',check=check2)
            choice = temp.emoji.split('\u20e3')[0]
            return choice

        async def pager(prefix, base, content_list, key):
            def check3(reaction,user):
                return user == message.author and reaction.message.id == sent.id and reaction.emoji in pointers

            async def paginator(sent,pointers,cursor,base,message_list):
                while True: 
                    reaction, user = await self.wait_for('reaction_add',check=check3)
                    op = pointers.index(reaction.emoji)
                    if op == 1 and cursor < len(message_list) - 1:
                        cursor += 1
                        await sent.edit(content=base+message_list[cursor])
                    elif op == 0 and cursor > 1:
                        cursor -= 1
                        await sent.edit(content=base+message_list[cursor])
                    else:
                        pass

            message_list = []
            if key == 0:
                for i in range(0, len(content_list), 10):
                    message_list.append('```{}\n'.format(prefix)+'\n'.join(content_list[i:i+10])+'```')
            else:
                message_list = ['```{}\n{}```'.format(prefix, work) for work in content_list]
            mess = base + message_list[0]
            sent = await message.channel.send(mess)
            pointers = ['👈','👉']
            for pointer in pointers:
                await sent.add_reaction(pointer)
            cursor = 0
            asyncio.ensure_future(paginator(sent,pointers,cursor,base,message_list))
            movie = await self.wait_for('message',check=check)
            await sent.delete()
            return movie

        sess = requests.Session()
        
        base_url = "https://spider.{}.hasura-app.io/".format(cluster)
        content = sess.get("{}connect?token={}".format(base_url,str(message.author.id))).json()
        sent_city = await message.channel.send("Hey {}, choose a city:\n```ml\n{}\n```".format(message.author.mention,content['cities']))
        city = await reactor(sent_city, 6)
        await sent_city.delete()
        sent_date = await message.channel.send("Now, pick a date:\n```ml\n{}\n```".format(content['dates']))
        date = await reactor(sent_date, 4)
        await sent_date.delete()
        delme = await message.channel.send('Fetching movies....:hourglass_flowing_sand:')
        movie_list = sess.get("{}city?reply={}".format(base_url,city)).text
        await delme.delete()
        base = "{}, choose a movie:\n".format(message.author.mention)
        movie_list = movie_list.split('\n')
        movie = await pager('ml', base, movie_list, 0)
        await movie.add_reaction('👍')
        await movie.add_reaction('⏳')
        url = "{}/movie?city={}&choice={}&date={}".format(base_url, city, movie.content, date)
        content = sess.get(url).json()
        await movie.clear_reactions()
        theatre_list = []
        for page in content:
            theatre_list.append(formatter(page))
        theatres = await pager('css', '{} here are the theatres:\n'.format(message.author.mention), theatre_list, 1)
    
    
    async def on_message(self, message):
        # we do not want the bot to reply to itself
        if message.author.id == self.user.id:
            return

        #----------------------------------------------------------------------------#
        # Don't worry about this part. We are just defining **kwargs for later use.
        cmd, *args = message.content.split(' ') # The first word is cmd, everything else is args. 
        cmd = cmd[len(self.prefix):].lower().strip() # For '$', cmd = cmd[1:0]. Eg. $help -> cmd = help
        handler = getattr(self,'cmd_{}'.format(cmd),None) # Checks if MyBot has an attribute called cmd_command (cmd_help).
        if not handler: # The command given doesn't exist in our code, so ignore it.
            return
        prms = inspect.signature(handler) # If attr is defined as async def help(a,b='test',c), prms = (a,b='test',c)
        params = prms.parameters.copy() # Copy since parameters are immutable.
        h_kwargs = {}                   # Dict for group testing all the attrs.
        if params.pop('message',None):
            h_kwargs['message'] = message
        if params.pop('channel',None):
            h_kwargs['channel'] = message.channel
        if params.pop('guild',None):
            h_kwargs['guild'] = message.guild
        if params.pop('mentions',None):
            h_kwargs['mentions'] = list(map(message.server.get_member, message.raw_mentions)) # Gets the user for the raw mention and repeats for every user in the guild.            
        if params.pop('args',None):
            h_kwargs['args'] = args

        # For remaining undefined keywords:
        for key, param in list(params.items()):
            if not args and param.default is not inspect.Parameter.empty: # Junk parameter present for attribute 
                params.pop(key) 
                continue        # We don't want that in our tester.

            if args:
                h_kwargs[key] = args.pop(0) # Binding keys to respective args.
                params.pop(key)

        # Time to call the test.
        res = await handler(**h_kwargs)
        if res and isinstance(res, Response): # Valid Response object
                content = res.content
                if res.reply:
                    content = '{},{}'.format(message.author.mention, content)

                sentmsg = await message.channel.send(content)

bot = ShowBot()    
bot.run(discord_token)
