import chalk from 'chalk';
import ora from 'ora';
import inquirer from 'inquirer';
import dayjs from 'dayjs';
import { writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
import { settings } from './config/settings.js';
import { whatsappClient } from './whatsapp/client.js';
import { parseMessage } from './whatsapp/formatter.js';
import { handleIncomingMessage } from './handlers/messageHandler.js';
import { initDb, getMessagesToday, searchMessages, getDistinctContacts, getMessageHistory, getAllSummaries } from './handlers/database.js';
import { generateDailySummary, scheduleSummary } from './summaries/dailySummary.js';
import { scanUnreadMessages } from './handlers/unreadScanner.js';
import { initLearningDb, getFeedbackStats } from './learning/learningDb.js';
import { showAllProfiles, getLearningProgress } from './learning/contactProfile.js';
import { runFullAnalysis } from './learning/styleAnalyzer.js';
import { onAutoAnalysis } from './learning/collector.js';
import { startHealthServer, setWhatsappStatus } from './health/server.js';
import { getPendingSuggestions, removeSuggestion, pendingCount, clearAll as clearSuggestions } from './handlers/suggestionQueue.js';

const LOGO = `
${chalk.green('╔══════════════════════════════════════╗')}
${chalk.green('║')}  ${chalk.bold.white('WhatsApp Assistant')} ${chalk.gray('by Maikeo')}        ${chalk.green('║')}
${chalk.green('║')}  ${chalk.cyan('Powered by Claude AI')}               ${chalk.green('║')}
${chalk.green('╚══════════════════════════════════════╝')}
`;

let currentMode = settings.botMode;
let isRunning = true;

async function showStatus() {
  const todayMsgs = getMessagesToday();
  const received = todayMsgs.filter(m => !m.from_me).length;
  const sent = todayMsgs.filter(m => m.from_me).length;

  console.log('\n' + chalk.bold('--- Status ---'));
  console.log(`${chalk.cyan('Modo:')} ${currentMode}`);
  console.log(`${chalk.cyan('Modelo IA:')} ${settings.aiModel}`);
  console.log(`${chalk.cyan('Mensagens hoje:')} ${received} recebidas, ${sent} enviadas`);
  console.log(`${chalk.cyan('Resumo agendado:')} ${settings.summaryTime}`);
  const progress = getLearningProgress();
  const bar = '█'.repeat(Math.floor(progress.percentage / 10)) + '░'.repeat(10 - Math.floor(progress.percentage / 10));
  console.log(`${chalk.cyan('Aprendizado:')} [${bar}] ${progress.percentage}% — ${progress.description}`);
  console.log(`${chalk.cyan('Respostas aprendidas:')} ${progress.totalPairs}`);

  // Show suggestion feedback stats
  const feedback = getFeedbackStats();
  if (feedback.total > 0) {
    console.log(`${chalk.cyan('Sugestoes:')} ${feedback.total} total | ${chalk.green(feedback.used + ' usadas')} | ${chalk.yellow(feedback.modified + ' modificadas')} | ${chalk.gray(feedback.ownResponse + ' proprias')}`);
    console.log(`${chalk.cyan('Precisao IA:')} ${feedback.accuracy}%`);
  }

  console.log(`${chalk.cyan('Hora atual:')} ${dayjs().format('HH:mm:ss')}`);
  console.log('');
}

async function showMenu() {
  const pending = pendingCount();
  const replyLabel = pending > 0
    ? chalk.bold.green(`✉  Responder sugestao (${pending} pendente${pending > 1 ? 's' : ''})`)
    : chalk.gray('✉  Responder sugestao (nenhuma pendente)');

  const choices = [
    { name: `${chalk.green('▶')} Ver status`, value: 'status' },
    { name: replyLabel, value: 'reply', disabled: pending === 0 ? '(sem sugestoes)' : false },
    { name: `${chalk.bold.cyan('📬')} Escanear nao lidas (resumo + sugestoes)`, value: 'unread' },
    { name: `${chalk.blue('💬')} Ver mensagens de hoje`, value: 'messages' },
    { name: `${chalk.yellow('🔄')} Mudar modo (atual: ${currentMode})`, value: 'mode' },
    { name: `${chalk.magenta('📋')} Gerar resumo do dia`, value: 'summary' },
    { name: `${chalk.white('🔍')} Buscar mensagens`, value: 'search' },
    { name: `${chalk.white('📖')} Historico por contato`, value: 'history' },
    { name: `${chalk.white('📂')} Exportar dados`, value: 'export' },
    { name: `${chalk.white('🧠')} Ver aprendizado (perfis)`, value: 'learning' },
    { name: `${chalk.white('🔄')} Analisar estilo agora`, value: 'analyze' },
    { name: `${chalk.red('✖')} Sair`, value: 'exit' },
  ];

  const { action } = await inquirer.prompt([{
    type: 'list',
    name: 'action',
    message: 'O que deseja fazer?',
    choices,
  }]);

  return action;
}

/**
 * Interactive flow to reply using a pending suggestion.
 * User picks a contact, then picks a suggestion (or types custom text).
 */
async function handleReply() {
  const pending = getPendingSuggestions();
  if (pending.length === 0) {
    console.log(chalk.yellow('\nNenhuma sugestao pendente.\n'));
    return;
  }

  // If only one contact, skip the contact selection step
  let entry;
  if (pending.length === 1) {
    entry = pending[0];
  } else {
    const { chatId } = await inquirer.prompt([{
      type: 'list',
      name: 'chatId',
      message: 'Para qual contato deseja responder?',
      choices: pending.map(p => ({
        name: `${p.contactName} — "${p.incomingMsg.substring(0, 50)}"`,
        value: p.chatId,
      })),
    }]);
    entry = pending.find(p => p.chatId === chatId);
  }

  console.log('\n' + chalk.bold(`Mensagem de ${entry.contactName}:`));
  console.log(chalk.gray(`  "${entry.incomingMsg}"\n`));

  // Build choices: numbered suggestions + custom option
  const choices = entry.suggestions.map((s, i) => ({
    name: `${i + 1}. [${s.label}] ${s.text}`,
    value: String(i),
  }));
  choices.push({ name: chalk.cyan('✏  Escrever resposta personalizada'), value: 'custom' });
  choices.push({ name: chalk.gray('↩  Ignorar (voltar ao menu)'), value: 'skip' });

  const { pick } = await inquirer.prompt([{
    type: 'list',
    name: 'pick',
    message: 'Qual resposta enviar?',
    choices,
  }]);

  if (pick === 'skip') {
    return;
  }

  let textToSend;
  if (pick === 'custom') {
    const { custom } = await inquirer.prompt([{
      type: 'input',
      name: 'custom',
      message: 'Digite sua resposta:',
    }]);
    if (!custom || !custom.trim()) {
      console.log(chalk.yellow('Resposta vazia — cancelado.\n'));
      return;
    }
    textToSend = custom.trim();
  } else {
    textToSend = entry.suggestions[Number(pick)].text;
  }

  // Send the message
  try {
    await whatsappClient.sendMessage(entry.chatId, textToSend);
    console.log(chalk.green(`\n✓ Mensagem enviada para ${entry.contactName}: "${textToSend.substring(0, 60)}"\n`));
    removeSuggestion(entry.chatId);
  } catch (err) {
    console.error(chalk.red(`Erro ao enviar mensagem: ${err.message}`));
  }
}

async function showTodayMessages() {
  const msgs = getMessagesToday();
  if (msgs.length === 0) {
    console.log(chalk.yellow('\nNenhuma mensagem registrada hoje.\n'));
    return;
  }

  const grouped = {};
  for (const msg of msgs) {
    const key = msg.contact_name || msg.chat_id;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(msg);
  }

  for (const [contact, messages] of Object.entries(grouped)) {
    console.log(chalk.bold.cyan(`\n--- ${contact} (${messages.length} msgs) ---`));
    for (const msg of messages.slice(-5)) {
      const time = dayjs.unix(msg.timestamp).format('HH:mm');
      const prefix = msg.from_me ? chalk.green('Voce') : chalk.white(contact);
      console.log(`  ${chalk.gray(time)} ${prefix}: ${msg.body.substring(0, 80)}`);
    }
  }
  console.log('');
}

async function handleSearch() {
  const { query } = await inquirer.prompt([{
    type: 'input',
    name: 'query',
    message: 'Buscar por:',
  }]);

  if (!query?.trim()) {
    console.log(chalk.yellow('Busca vazia — cancelado.\n'));
    return;
  }

  const results = searchMessages(query.trim(), 30);
  if (results.length === 0) {
    console.log(chalk.yellow(`\nNenhum resultado para "${query}".\n`));
    return;
  }

  console.log(chalk.bold(`\n--- ${results.length} resultado(s) para "${query}" ---\n`));
  for (const msg of results) {
    const time = dayjs.unix(msg.timestamp).format('DD/MM HH:mm');
    const prefix = msg.from_me ? chalk.green('Voce') : chalk.cyan(msg.contact_name);
    const body = msg.body.substring(0, 120);
    console.log(`  ${chalk.gray(time)} ${prefix}: ${body}`);
  }
  console.log('');
}

async function handleHistory() {
  const contacts = getDistinctContacts();
  if (contacts.length === 0) {
    console.log(chalk.yellow('\nNenhum contato registrado ainda.\n'));
    return;
  }

  const choices = contacts.slice(0, 20).map(c => ({
    name: `${c.contact_name} (${c.msg_count} msgs, ultimo: ${dayjs.unix(c.last_msg).format('DD/MM HH:mm')})`,
    value: c.contact_name,
  }));

  const { contact } = await inquirer.prompt([{
    type: 'list',
    name: 'contact',
    message: 'Selecione o contato:',
    choices,
  }]);

  const msgs = getMessageHistory(contact, 50);
  console.log(chalk.bold(`\n--- Historico: ${contact} (${msgs.length} msgs) ---\n`));
  for (const msg of msgs) {
    const time = dayjs.unix(msg.timestamp).format('DD/MM HH:mm');
    const prefix = msg.from_me ? chalk.green('Voce') : chalk.cyan(contact);
    console.log(`  ${chalk.gray(time)} ${prefix}: ${msg.body.substring(0, 150)}`);
  }
  console.log('');
}

async function handleExport() {
  const { exportType } = await inquirer.prompt([{
    type: 'list',
    name: 'exportType',
    message: 'O que deseja exportar?',
    choices: [
      { name: 'Mensagens de hoje (CSV)', value: 'today_csv' },
      { name: 'Historico de contato (TXT)', value: 'contact_txt' },
      { name: 'Todos os resumos (TXT)', value: 'summaries' },
      { name: 'Cancelar', value: 'cancel' },
    ],
  }]);

  if (exportType === 'cancel') return;

  const exportDir = join(__dirname, '../exports');
  mkdirSync(exportDir, { recursive: true });
  const timestamp = dayjs().format('YYYY-MM-DD_HH-mm');

  if (exportType === 'today_csv') {
    const msgs = getMessagesToday();
    if (msgs.length === 0) {
      console.log(chalk.yellow('\nNenhuma mensagem hoje para exportar.\n'));
      return;
    }
    const header = 'timestamp,contact_name,from_me,category,body';
    const rows = msgs.map(m => {
      const time = dayjs.unix(m.timestamp).format('YYYY-MM-DD HH:mm:ss');
      const body = `"${(m.body || '').replace(/"/g, '""')}"`;
      return `${time},${m.contact_name},${m.from_me ? 'sim' : 'nao'},${m.category || ''},${body}`;
    });
    const filePath = join(exportDir, `mensagens_${timestamp}.csv`);
    writeFileSync(filePath, [header, ...rows].join('\n'), 'utf-8');
    console.log(chalk.green(`\nExportado ${msgs.length} mensagens para: ${filePath}\n`));
  }

  if (exportType === 'contact_txt') {
    const contacts = getDistinctContacts();
    if (contacts.length === 0) {
      console.log(chalk.yellow('\nNenhum contato registrado.\n'));
      return;
    }
    const { contact } = await inquirer.prompt([{
      type: 'list',
      name: 'contact',
      message: 'Qual contato?',
      choices: contacts.slice(0, 20).map(c => ({ name: c.contact_name, value: c.contact_name })),
    }]);
    const msgs = getMessageHistory(contact, 500);
    const lines = msgs.map(m => {
      const time = dayjs.unix(m.timestamp).format('DD/MM/YY HH:mm');
      const who = m.from_me ? 'Voce' : contact;
      return `[${time}] ${who}: ${m.body}`;
    });
    const filePath = join(exportDir, `${contact.replace(/[^a-zA-Z0-9]/g, '_')}_${timestamp}.txt`);
    writeFileSync(filePath, lines.join('\n'), 'utf-8');
    console.log(chalk.green(`\nExportado ${msgs.length} mensagens de ${contact} para: ${filePath}\n`));
  }

  if (exportType === 'summaries') {
    const summaries = getAllSummaries(30);
    if (summaries.length === 0) {
      console.log(chalk.yellow('\nNenhum resumo disponivel.\n'));
      return;
    }
    const lines = summaries.map(s => `\n=== ${s.date} ===\n${s.content}`);
    const filePath = join(exportDir, `resumos_${timestamp}.txt`);
    writeFileSync(filePath, lines.join('\n\n'), 'utf-8');
    console.log(chalk.green(`\nExportado ${summaries.length} resumos para: ${filePath}\n`));
  }
}

async function changeMode() {
  const { mode } = await inquirer.prompt([{
    type: 'list',
    name: 'mode',
    message: 'Escolha o modo:',
    choices: [
      { name: 'auto - Responde automaticamente', value: 'auto' },
      { name: 'suggest - Sugere respostas para voce aprovar', value: 'suggest' },
      { name: 'summary - Apenas registra e resume (nao responde)', value: 'summary' },
    ],
    default: currentMode,
  }]);

  currentMode = mode;
  if (mode !== 'suggest') clearSuggestions();
  console.log(chalk.green(`\nModo alterado para: ${mode}\n`));
}

async function onMessage(msg) {
  try {
    const parsed = parseMessage(msg);
    const contactName = parsed.fromName || parsed.from;
    const preview = parsed.body?.substring(0, 60) || '[midia]';

    if (msg.fromMe) {
      // Capture user's own messages for learning
      console.log(
        chalk.gray(dayjs().format('HH:mm:ss')) + ' ' +
        chalk.green('[Voce]') + ' ' +
        chalk.gray(preview)
      );
    } else {
      console.log(
        chalk.gray(dayjs().format('HH:mm:ss')) + ' ' +
        chalk.cyan(`[${contactName}]`) + ' ' +
        preview
      );
    }

    // Handler processes BOTH incoming and outgoing (for learning)
    await handleIncomingMessage(msg, {
      mode: currentMode,
      whatsappClient,
    });
  } catch (err) {
    console.error(chalk.red('Erro ao processar mensagem:'), err.message);
  }
}

async function main() {
  console.clear();
  console.log(LOGO);

  // Validate API key
  if (!settings.anthropicApiKey) {
    console.log(chalk.red.bold('\nERRO: ANTHROPIC_API_KEY nao configurada!'));
    console.log(chalk.yellow('1. Copie .env.example para .env'));
    console.log(chalk.yellow('2. Adicione sua chave da API Claude'));
    console.log(chalk.yellow('   Pegue em: https://console.anthropic.com/\n'));
    process.exit(1);
  }

  // Init database
  const dbSpinner = ora('Inicializando bancos de dados...').start();
  initDb();
  initLearningDb();
  dbSpinner.succeed('Bancos de dados prontos (mensagens + aprendizado)');

  // Start health-check HTTP server
  const healthPort = parseInt(process.env.HEALTH_PORT || '3100');
  const healthServer = startHealthServer(healthPort);

  // Register auto-analysis callback (triggers after every 20 new learned pairs)
  onAutoAnalysis(async () => {
    const result = await runFullAnalysis();
    console.log(
      chalk.magenta('[Auto-Aprendizado]') + ' ' +
      chalk.green(`${result.contactsAnalyzed} perfis atualizados automaticamente`)
    );
  });

  // Connect WhatsApp
  const waSpinner = ora('Conectando ao WhatsApp...').start();

  try {
    whatsappClient.on('qr', () => {
      waSpinner.stop();
      console.log(chalk.yellow('\nEscaneie o QR code acima com seu WhatsApp:\n'));
      console.log(chalk.gray('WhatsApp > Dispositivos conectados > Conectar dispositivo\n'));
    });

    whatsappClient.on('ready', () => {
      waSpinner.succeed('WhatsApp conectado!');
      setWhatsappStatus('connected');
    });

    whatsappClient.on('disconnected', (reason) => {
      setWhatsappStatus('disconnected');
      console.log(chalk.red(`\nWhatsApp desconectado: ${reason}`));
      console.log(chalk.yellow('Tentando reconectar automaticamente...'));
    });

    whatsappClient.onMessage(onMessage);

    // Returns a promise that resolves when ready
    await new Promise((resolve, reject) => {
      whatsappClient.on('ready', resolve);
      whatsappClient.on('auth_failure', reject);
      whatsappClient.initialize();
    });
  } catch (err) {
    waSpinner.fail('Falha ao conectar WhatsApp');
    console.error(chalk.red(err.message));
    process.exit(1);
  }

  // Schedule daily summary (resumo automatico no horario configurado)
  const cancelSummary = scheduleSummary(settings.summaryTime);

  // Auto-scan unread messages on connect (resumo automatico ao conectar)
  console.log('');
  await scanUnreadMessages(whatsappClient);

  // Show initial status
  await showStatus();

  // Interactive menu loop
  while (isRunning) {
    try {
      const action = await showMenu();

      switch (action) {
        case 'status':
          await showStatus();
          break;
        case 'reply':
          await handleReply();
          break;
        case 'unread':
          await scanUnreadMessages(whatsappClient);
          break;
        case 'messages':
          await showTodayMessages();
          break;
        case 'mode':
          await changeMode();
          break;
        case 'summary': {
          const summarySpinner = ora('Gerando resumo...').start();
          const summary = await generateDailySummary();
          summarySpinner.succeed('Resumo gerado!');
          console.log('\n' + chalk.bold('=== Resumo do Dia ==='));
          console.log(summary);
          console.log('');
          break;
        }
        case 'search':
          await handleSearch();
          break;
        case 'history':
          await handleHistory();
          break;
        case 'export':
          await handleExport();
          break;
        case 'learning':
          showAllProfiles();
          break;
        case 'analyze': {
          const analyzeSpinner = ora('Analisando seu estilo de comunicacao...').start();
          const result = await runFullAnalysis();
          analyzeSpinner.succeed(`Analise completa! ${result.contactsAnalyzed} perfis atualizados.`);
          break;
        }
        case 'exit':
          isRunning = false;
          break;
      }
    } catch (err) {
      if (err.name === 'ExitPromptError') {
        isRunning = false;
      } else {
        console.error(chalk.red('Erro:'), err.message);
      }
    }
  }

  // Cleanup
  cancelSummary();
  healthServer.close();
  whatsappClient.disableAutoReconnect();
  console.log(chalk.yellow('\nDesligando...'));
  if (whatsappClient.client) await whatsappClient.client.destroy();
  console.log(chalk.green('Ate mais!\n'));
  process.exit(0);
}

// Handle Ctrl+C gracefully
process.on('SIGINT', () => {
  console.log(chalk.yellow('\n\nEncerrando...'));
  isRunning = false;
});

main().catch(err => {
  console.error(chalk.red('Erro fatal:'), err);
  process.exit(1);
});
