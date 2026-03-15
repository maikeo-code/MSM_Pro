import chalk from 'chalk';
import ora from 'ora';
import dayjs from 'dayjs';
import { generateSummary, suggestResponse, classifyMessage } from '../ai/claude.js';
import { settings } from '../config/settings.js';

/**
 * Scan all unread chats and generate a categorized summary with suggestions.
 * IMPORTANT: Does NOT mark messages as read - they stay unread.
 *
 * @param {import('../whatsapp/client.js').WhatsAppClient} waClient
 * @returns {Promise<void>}
 */
export async function scanUnreadMessages(waClient) {
  const spinner = ora('Escaneando mensagens nao lidas...').start();

  try {
    const chats = await waClient.getChats();

    // Filter only chats with unread messages
    const unreadChats = chats.filter(chat => chat.unreadCount > 0);

    if (unreadChats.length === 0) {
      spinner.succeed('Nenhuma mensagem nao lida.');
      return;
    }

    spinner.text = `Encontradas ${unreadChats.length} conversas nao lidas. Analisando...`;

    // Categorize conversations
    const categories = {
      financeiro: { label: 'FINANCEIRO (Bancos/Pagamentos)', chats: [] },
      trabalho: { label: 'TRABALHO (Fornecedores/Clientes)', chats: [] },
      pessoal: { label: 'PESSOAL (Amigos/Familia)', chats: [] },
      grupos: { label: 'GRUPOS', chats: [] },
      notificacoes: { label: 'NOTIFICACOES/SPAM', chats: [] },
    };

    // Known financial contacts (banks, payment services)
    const financialKeywords = ['itau', 'bradesco', 'nubank', 'inter', 'caixa', 'santander', 'banco', 'bb ', 'sicoob', 'sicredi', 'mercado pago', 'picpay', 'pagseguro', 'stone', 'cielo', 'pix', 'boleto', 'fatura', 'cartao'];

    for (const chat of unreadChats) {
      // Fetch unread messages (get last N messages where N = unreadCount, max 50)
      const limit = Math.min(chat.unreadCount, 50);
      const messages = await chat.fetchMessages({ limit });

      // Get only unread (not fromMe) recent messages
      const unreadMsgs = messages
        .filter(m => !m.fromMe && m.body?.trim())
        .slice(-limit)
        .map(m => ({
          from: m.from,
          body: m.body,
          timestamp: m.timestamp,
          fromMe: false,
        }));

      if (unreadMsgs.length === 0) continue;

      const contactName = chat.name || chat.id._serialized;
      const isGroup = chat.isGroup;
      const preview = unreadMsgs.map(m => m.body).join(' | ').substring(0, 200);

      const chatInfo = {
        name: contactName,
        unreadCount: chat.unreadCount,
        messages: unreadMsgs,
        preview,
        chatId: chat.id._serialized,
      };

      // Categorize
      if (isGroup) {
        categories.grupos.chats.push(chatInfo);
      } else {
        const nameLower = contactName.toLowerCase();
        const contentLower = preview.toLowerCase();

        const isFinancial = financialKeywords.some(kw =>
          nameLower.includes(kw) || contentLower.includes(kw)
        );

        if (isFinancial) {
          categories.financeiro.chats.push(chatInfo);
        } else {
          // Use AI to classify if work or personal
          try {
            const classification = await classifyMessage(unreadMsgs[0].body, contactName);
            if (classification?.category === 'work') {
              categories.trabalho.chats.push(chatInfo);
            } else if (classification?.category === 'spam' || classification?.category === 'notification') {
              categories.notificacoes.chats.push(chatInfo);
            } else {
              categories.pessoal.chats.push(chatInfo);
            }
          } catch {
            categories.pessoal.chats.push(chatInfo);
          }
        }
      }
    }

    spinner.succeed(`${unreadChats.length} conversas nao lidas analisadas!`);

    // Display categorized summary
    console.log('\n' + chalk.bold.white('╔══════════════════════════════════════════════════╗'));
    console.log(chalk.bold.white('║') + chalk.bold.cyan('       RESUMO DE MENSAGENS NAO LIDAS              ') + chalk.bold.white('║'));
    console.log(chalk.bold.white('╚══════════════════════════════════════════════════╝'));

    let totalUnread = 0;

    for (const [key, category] of Object.entries(categories)) {
      if (category.chats.length === 0) continue;

      const catCount = category.chats.reduce((sum, c) => sum + c.unreadCount, 0);
      totalUnread += catCount;

      // Category header with color based on type
      const colorFn = key === 'financeiro' ? chalk.yellow
        : key === 'trabalho' ? chalk.blue
        : key === 'pessoal' ? chalk.green
        : key === 'grupos' ? chalk.magenta
        : chalk.gray;

      console.log('\n' + colorFn.bold(`━━━ ${category.label} (${catCount} msgs) ━━━`));

      for (const chatInfo of category.chats) {
        console.log('');
        console.log(colorFn(`  📌 ${chatInfo.name}`) + chalk.gray(` (${chatInfo.unreadCount} nao lidas)`));

        // Show last 3 messages as preview
        const recentMsgs = chatInfo.messages.slice(-3);
        for (const m of recentMsgs) {
          const time = dayjs.unix(m.timestamp).format('HH:mm');
          const bodyPreview = m.body.substring(0, 100);
          console.log(chalk.gray(`    ${time} `) + chalk.white(bodyPreview));
        }

        // Generate AI suggestion for this chat
        try {
          const context = chatInfo.messages.map(m => ({ fromMe: m.fromMe, body: m.body }));
          const lastMsg = chatInfo.messages[chatInfo.messages.length - 1].body;
          const suggestions = await suggestResponse(context, lastMsg, chatInfo.name);

          if (suggestions && suggestions.length > 0) {
            console.log(chalk.cyan('    💡 Sugestoes de resposta:'));
            suggestions.forEach((s, i) => {
              console.log(chalk.cyan(`       ${i + 1}. [${s.label}] `) + chalk.white(s.text));
            });
          }
        } catch {
          // Skip suggestions on error
        }
      }
    }

    // Footer
    console.log('\n' + chalk.bold.white('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'));
    console.log(chalk.bold.white(`  Total: ${totalUnread} mensagens nao lidas em ${unreadChats.length} conversas`));
    console.log(chalk.gray('  As mensagens continuam como NAO LIDAS no WhatsApp'));
    console.log(chalk.bold.white('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'));

  } catch (err) {
    spinner.fail('Erro ao escanear mensagens');
    console.error(chalk.red(err.message));
  }
}
