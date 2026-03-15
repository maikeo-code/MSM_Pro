import 'dotenv/config';

export const settings = {
  anthropicApiKey: process.env.ANTHROPIC_API_KEY,
  aiModel: process.env.AI_MODEL || 'claude-haiku-4-5-20251001',
  myName: process.env.MY_NAME || 'User',
  botMode: process.env.BOT_MODE || 'suggest', // auto | suggest | summary
  blacklistContacts: (process.env.BLACKLIST_CONTACTS || '').split(',').filter(Boolean),
  vipContacts: (process.env.VIP_CONTACTS || '').split(',').filter(Boolean),
  summaryTime: process.env.SUMMARY_TIME || '22:00',
  maxTokens: parseInt(process.env.MAX_TOKENS_PER_RESPONSE || '500'),
  language: process.env.LANGUAGE || 'pt-BR',
};
