// Isolated imvu.js compatibility probe. Does not change CrowBot radio or chat.
// npm install imvu.js
// Set IMVUJS_TOKEN in your environment. Never commit a token.
const IMVU = require('imvu.js');
const token = process.env.IMVUJS_TOKEN;
if (!token) { console.error('Set IMVUJS_TOKEN first'); process.exit(2); }
const bot = new IMVU({show_online:true});
bot.on('ready', () => console.log('READY', JSON.stringify({id:bot.id,room_id:bot.room?.id,display_name:bot.display_name})));
bot.on('join', user => console.log('JOIN', JSON.stringify({id:user.id,username:user.username,display_name:user.display_name,isMod:user.isMod,bot:user.bot})));
bot.on('message', msg => console.log('MESSAGE', JSON.stringify({id:msg.user?.id,username:msg.user?.username,display_name:msg.user?.display_name,isMod:msg.user?.isMod,bot:msg.user?.bot,content:msg.content})));
bot.on('leave', user => console.log('LEAVE', JSON.stringify({id:user.id,username:user.username,display_name:user.display_name})));
bot.on('error', err => console.error('ERROR',err?.message||String(err)));
bot.login(token);
