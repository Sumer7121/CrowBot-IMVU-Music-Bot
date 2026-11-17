// Standalone diagnostic. Never prints the API token or sends messages.
// Use only in an IMVU room you own and are authorized to connect to.
const IMVU = require('imvu.js');
const token = process.env.IMVUJS_TOKEN;
if (!token) {
  console.error('Set IMVUJS_TOKEN in your terminal before running.');
  process.exit(1);
}
const client = new IMVU({});
function safeUser(user) {
  if (!user) return null;
  return {
    id: user.id ?? null,
    username: user.username ?? null,
    display_name: user.display_name ?? null,
    isMod: user.isMod ?? null,
    bot: user.bot ?? null
  };
}
client.on('ready', () => {
  console.log('[READY]', { bot_id: client.id ?? null, room_id: client.room?.id ?? null });
});
client.on('join', (user) => console.log('[JOIN]', safeUser(user)));
client.on('leave', (user) => console.log('[LEAVE]', safeUser(user)));
client.on('message', (message) => {
  if (message?.user?.bot) return;
  console.log('[CHAT]', {
    user: safeUser(message?.user),
    // Show commands only; avoid logging other people's private conversation.
    command: String(message?.content ?? '').startsWith('!')
      ? String(message.content).slice(0, 120) : null
  });
});
client.on('error', (error) => console.error('[ERROR]', error?.message || String(error)));
process.on('SIGINT', () => { console.log('Stopping diagnostic.'); process.exit(0); });
client.login(token);
