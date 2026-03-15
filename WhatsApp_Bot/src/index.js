import chalk from 'chalk';
import ora from 'ora';
import inquirer from 'inquirer';
import dayjs from 'dayjs';
import { settings } from './config/settings.js';
import { whatsappClient } from './whatsapp/client.js';
import { parseMessage } from './whatsapp/formatter.js';
import { handleIncomingMessage } from './handlers/messageHandler.js';
import { initDb, getMessagesToday } from './handlers/database.js';
import { generateDailySummary, scheduleSummary } from './summaries/dailySummary.js';
import { scanUnreadMessages } from './handlers/unreadScanner.js';
import { initLearningDb } from './learning/learningDb.js';
import { showAllProfiles, getLearningProgress } from './learning/contactProfile.js';
import { runFullAnalysis } from './learning/styleAnalyzer.js';

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
  console.log(`${chalk.cyan('Hora atual:')} ${dayjs().format('HH:mm:ss')}`);
  console.log('');
}

async function showMenu() {
  const { action } = await inquirer.prompt([{
    type: 'list',
    name: 'action',
    message: 'O que deseja fazer?',
    choices: [
      { name: `${chalk.green('▶')} Ver status`, value: 'status' },
      { name: `${chalk.bold.cyan('📬')} Escanear nao lidas (resumo + sugestoes)`, value: 'unread' },
      { name: `${chalk.blue('💬')} Ver mensagens de hoje`, value: 'messages' },
      { name: `${chalk.yellow('🔄')} Mudar modo (atual: ${currentMode})`, value: 'mode' },
      { name: `${chalk.magenta('📋')} Gerar resumo do dia`, value: 'summary' },
      { name: `${chalk.white('🧠')} Ver aprendizado (perfis)`, value: 'learning' },
      { name: `${chalk.white('🔄')} Analisar estilo agora`, value: 'analyze' },
      { name: `${chalk.red('✖')} Sair`, value: 'exit' },
    ],
  }]);

  return action;
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
      const time = dayjs(msg.timestamp).format('HH:mm');
      const prefix = msg.from_me ? chalk.green('Voce') : chalk.white(contact);
      console.log(`  ${chalk.gray(time)} ${prefix}: ${msg.body.substring(0, 80)}`);
    }
  }
  console.log('');
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
    });

    whatsappClient.on('disconnected', (reason) => {
      console.log(chalk.red(`\nWhatsApp desconectado: ${reason}`));
      console.log(chalk.yellow('Reinicie o app para reconectar.\n'));
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
  console.log(chalk.yellow('\nDesligando...'));
  if (whatsappClient.client) await whatsappClient.client.destroy();
  console.log(chalk.green('Ate mais! 👋\n'));
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
