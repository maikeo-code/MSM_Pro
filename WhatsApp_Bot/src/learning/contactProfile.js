import chalk from 'chalk';
import { getAllContactStyles, getContactStyle, getTopVocabulary, getResponsePairCount } from './learningDb.js';
import { getResponsePairs, getAllResponsePairs } from './learningDb.js';

/**
 * Display a formatted profile for a specific contact.
 * Shows what the bot has learned about how the user communicates with them.
 *
 * @param {string} contactName
 */
export function showContactProfile(contactName) {
  const style = getContactStyle(contactName);
  const pairs = getResponsePairs(contactName, 10);

  if (!style && pairs.length === 0) {
    console.log(chalk.yellow(`\n  Nenhum dado de aprendizado para "${contactName}" ainda.`));
    console.log(chalk.gray('  O bot precisa observar suas respostas primeiro.\n'));
    return;
  }

  console.log('\n' + chalk.bold.cyan(`  ━━━ Perfil: ${contactName} ━━━`));

  if (style) {
    const categoryIcon = style.category === 'work' ? '🏢'
      : style.category === 'financial' ? '💰'
      : '👤';

    const greetings = Array.isArray(style.greeting_words) ? style.greeting_words : [];
    const farewells = Array.isArray(style.farewell_words) ? style.farewell_words : [];
    const phrases = Array.isArray(style.common_phrases) ? style.common_phrases : [];

    console.log(`  ${categoryIcon} Categoria: ${chalk.white(style.category)}`);
    console.log(`  🎭 Tom: ${chalk.white(style.tone)}`);
    if (greetings.length) console.log(`  👋 Cumprimentos: ${chalk.green(greetings.join(', '))}`);
    if (farewells.length) console.log(`  🤝 Despedidas: ${chalk.green(farewells.join(', '))}`);
    if (phrases.length) console.log(`  💬 Frases comuns: ${chalk.green(phrases.join(', '))}`);
    console.log(`  😀 Emojis: ${chalk.white(style.emoji_usage)}`);
    console.log(`  📏 Tamanho medio: ${chalk.white(style.avg_response_length + ' chars')}`);
    console.log(`  ⚡ Padrao: ${chalk.white(style.response_pattern)}`);
    console.log(`  📊 Interacoes: ${chalk.white(style.total_interactions)}`);
  }

  if (pairs.length > 0) {
    console.log(chalk.gray('\n  Ultimas interacoes:'));
    for (const pair of pairs.slice(-5)) {
      console.log(chalk.gray(`    Recebido: "${pair.incoming_msg.substring(0, 60)}"`));
      console.log(chalk.green(`    Resposta: "${pair.user_response.substring(0, 60)}"`));
      console.log(chalk.gray(`    Tempo: ${pair.response_time_seconds}s`));
      console.log('');
    }
  }
}

/**
 * Display a summary of all learned contact profiles.
 */
export function showAllProfiles() {
  const styles = getAllContactStyles();
  const allPairs = getAllResponsePairs(1000);

  if (styles.length === 0 && allPairs.length === 0) {
    console.log(chalk.yellow('\n  Nenhum dado de aprendizado ainda.'));
    console.log(chalk.gray('  Use o WhatsApp normalmente. O bot vai observar suas respostas'));
    console.log(chalk.gray('  e aprender seu estilo automaticamente.\n'));
    return;
  }

  console.log('\n' + chalk.bold.white('╔══════════════════════════════════════════════════╗'));
  console.log(chalk.bold.white('║') + chalk.bold.cyan('         BASE DE CONHECIMENTO DO BOT              ') + chalk.bold.white('║'));
  console.log(chalk.bold.white('╚══════════════════════════════════════════════════╝'));

  // Stats
  const uniqueContacts = [...new Set(allPairs.map(p => p.contact_name))];
  console.log(`\n  ${chalk.cyan('Total de respostas aprendidas:')} ${chalk.bold.white(allPairs.length)}`);
  console.log(`  ${chalk.cyan('Contatos com perfil:')} ${chalk.bold.white(styles.length)}`);
  console.log(`  ${chalk.cyan('Contatos observados:')} ${chalk.bold.white(uniqueContacts.length)}`);

  // Group by category
  const workStyles = styles.filter(s => s.category === 'work');
  const personalStyles = styles.filter(s => s.category === 'personal');
  const financialStyles = styles.filter(s => s.category === 'financial');

  if (workStyles.length > 0) {
    console.log(chalk.blue.bold('\n  ━━━ 🏢 TRABALHO ━━━'));
    for (const s of workStyles) {
      const phrases = Array.isArray(s.common_phrases) ? s.common_phrases : [];
      console.log(`  ${chalk.white(s.contact_name)} - ${s.tone} (${s.total_interactions} msgs)`);
      if (phrases.length) console.log(chalk.gray(`    Frases: ${phrases.slice(0, 3).join(', ')}`));
    }
  }

  if (personalStyles.length > 0) {
    console.log(chalk.green.bold('\n  ━━━ 👤 PESSOAL ━━━'));
    for (const s of personalStyles) {
      const phrases = Array.isArray(s.common_phrases) ? s.common_phrases : [];
      console.log(`  ${chalk.white(s.contact_name)} - ${s.tone} (${s.total_interactions} msgs)`);
      if (phrases.length) console.log(chalk.gray(`    Frases: ${phrases.slice(0, 3).join(', ')}`));
    }
  }

  if (financialStyles.length > 0) {
    console.log(chalk.yellow.bold('\n  ━━━ 💰 FINANCEIRO ━━━'));
    for (const s of financialStyles) {
      console.log(`  ${chalk.white(s.contact_name)} - ${s.tone} (${s.total_interactions} msgs)`);
    }
  }

  // Show vocabulary
  const vocab = getTopVocabulary(15);
  if (vocab.length > 0) {
    console.log(chalk.magenta.bold('\n  ━━━ 📝 SEU VOCABULARIO ━━━'));
    const greetings = vocab.filter(v => v.context === 'greeting').map(v => v.word_or_phrase);
    const expressions = vocab.filter(v => v.context === 'expression').map(v => v.word_or_phrase);
    const farewells = vocab.filter(v => v.context === 'farewell').map(v => v.word_or_phrase);

    if (greetings.length) console.log(`  Cumprimentos: ${chalk.green(greetings.join(', '))}`);
    if (expressions.length) console.log(`  Expressoes: ${chalk.green(expressions.join(', '))}`);
    if (farewells.length) console.log(`  Despedidas: ${chalk.green(farewells.join(', '))}`);
  }

  console.log('\n' + chalk.bold.white('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'));
}

/**
 * Get learning progress as a percentage and description.
 * @returns {{ percentage: number, description: string, totalPairs: number }}
 */
export function getLearningProgress() {
  const total = getResponsePairCount();
  const styles = getAllContactStyles();

  if (total === 0) {
    return { percentage: 0, description: 'Sem dados - comece a usar o WhatsApp', totalPairs: 0 };
  }
  if (total < 20) {
    return { percentage: 15, description: 'Iniciando - observando suas respostas', totalPairs: total };
  }
  if (total < 50) {
    return { percentage: 30, description: 'Aprendendo - reconhecendo padroes', totalPairs: total };
  }
  if (total < 100) {
    return { percentage: 50, description: 'Progredindo - entendendo seu estilo', totalPairs: total };
  }
  if (total < 200) {
    return { percentage: 70, description: 'Avancado - respostas ficando parecidas', totalPairs: total };
  }
  if (total < 500) {
    return { percentage: 85, description: 'Experiente - alta precisao', totalPairs: total };
  }
  return { percentage: 95, description: 'Mestre - respostas quase identicas as suas', totalPairs: total };
}
